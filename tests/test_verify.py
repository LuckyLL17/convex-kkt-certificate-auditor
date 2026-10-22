"""外部契约的行为验证；仅经命令行调用候选程序。"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
PROGRAM = APP_DIR / "src" / "verify.py"


def invoke(tmp_path, payload=None, raw=None, output_name="report.json"):
    """以独立文件运行程序并保留标准流和输出路径。"""
    source = tmp_path / "certificate.json"
    if raw is None:
        source.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")
    else:
        source.write_text(raw, encoding="utf-8")
    destination = tmp_path / output_name
    result = subprocess.run(
        [sys.executable, str(PROGRAM), "--input", str(source), "--output", str(destination)],
        text=True, capture_output=True, check=False,
    )
    return result, destination


def certified_interior():
    return {"A": [[1, 0], [0, 1]], "b": [3, -2], "c": [0, 0],
            "lower": [0, -3], "x": [3, -2], "multipliers": [0, 0]}


def report(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_input_rejected(result, destination):
    assert result.returncode != 0
    assert result.stderr.startswith("E_INPUT:")
    assert destination.read_bytes() == b"prior-report\n"


def test_certifies_interior_stationary_certificate(tmp_path):
    """R1：内部可行的零梯度证书必须通过核心 KKT 审计。"""
    result, destination = invoke(tmp_path, certified_interior())
    assert result.returncode == 0
    actual = report(destination)
    assert actual["status"] == "CERTIFIED"
    assert actual["active_lower"] == []
    assert actual["objective"] == pytest.approx(0.0)
    assert actual["residual_inf"] == pytest.approx(0.0)


def test_certifies_active_constraint_with_positive_multiplier(tmp_path):
    """R1：活跃下界的正乘子必须按 lower-x<=0 的约定被接受。"""
    payload = {"A": [[1]], "b": [5], "c": [7], "lower": [0], "x": [0], "multipliers": [2]}
    result, destination = invoke(tmp_path, payload)
    assert result.returncode == 0
    actual = report(destination)
    assert actual["status"] == "CERTIFIED"
    assert actual["active_lower"] == [0]
    assert actual["objective"] == pytest.approx(12.5)
    assert actual["residual_inf"] == pytest.approx(0.0)


def test_rejects_primal_violation_and_reports_maximum_residual(tmp_path):
    """R1：越过下界的候选必须正常生成 REJECTED 与非负违反量。"""
    payload = {"A": [[1]], "b": [0], "c": [0], "lower": [1], "x": [0.75], "multipliers": [0]}
    result, destination = invoke(tmp_path, payload)
    assert result.returncode == 0
    actual = report(destination)
    assert actual["status"] == "REJECTED"
    assert actual["residual_inf"] >= 0.25
    assert actual["objective"] == pytest.approx(0.28125)


def test_rejects_stationarity_sign_or_gradient_mismatch(tmp_path):
    """R1：梯度与乘子不相等时，即使其余条件可行也不能认证。"""
    payload = {"A": [[1]], "b": [0], "c": [0], "lower": [0], "x": [1], "multipliers": [0]}
    result, destination = invoke(tmp_path, payload)
    assert result.returncode == 0
    actual = report(destination)
    assert actual["status"] == "REJECTED"
    assert actual["residual_inf"] == pytest.approx(1.0)


def test_rejects_nonzero_complementarity(tmp_path):
    """R1：正乘子与松弛量同时非零必须触发互补性拒绝。"""
    payload = {"A": [[1]], "b": [0], "c": [1], "lower": [0], "x": [1], "multipliers": [2]}
    result, destination = invoke(tmp_path, payload)
    assert result.returncode == 0
    actual = report(destination)
    assert actual["status"] == "REJECTED"
    assert actual["residual_inf"] >= 2.0


def test_marks_near_lower_coordinate_active_under_public_tolerance(tmp_path):
    """R2：数学上不同但落在容差内的坐标仍须稳定标记为活跃。"""
    payload = {"A": [[1]], "b": [1e-9], "c": [0], "lower": [0], "x": [1e-9],
               "multipliers": [0], "tolerance": 1e-8}
    result, destination = invoke(tmp_path, payload)
    assert result.returncode == 0
    actual = report(destination)
    assert actual["status"] == "CERTIFIED"
    assert actual["active_lower"] == [0]


def test_rejects_out_of_range_tolerance_without_replacing_report(tmp_path):
    """R2/R3：越界容差属于输入错误，并必须保留已有报告字节。"""
    payload = certified_interior() | {"tolerance": 1e-6 / 10000000}
    output = tmp_path / "report.json"
    output.write_bytes(b"prior-report\n")
    result, destination = invoke(tmp_path, payload)
    assert_input_rejected(result, destination)


def test_rejects_inconsistent_matrix_and_vector_dimensions(tmp_path):
    """R3：矩阵列数与变量向量长度不一致时不可进入数学审计。"""
    payload = certified_interior() | {"c": [0]}
    output = tmp_path / "report.json"
    output.write_bytes(b"prior-report\n")
    result, destination = invoke(tmp_path, payload)
    assert_input_rejected(result, destination)


def test_rejects_boolean_and_nonfinite_values(tmp_path):
    """R3：布尔伪数和非有限 JSON 数值均必须被拒收且无输出副作用。"""
    for payload in (certified_interior() | {"x": [True, -2]}, certified_interior() | {"c": [float("nan"), 0]}):
        output = tmp_path / "report.json"
        output.write_bytes(b"prior-report\n")
        result, destination = invoke(tmp_path, payload)
        assert_input_rejected(result, destination)


def test_rejects_missing_or_extra_top_level_keys(tmp_path):
    """R3：顶层对象必须严格遵守公开键集合，不能静默忽略未知字段。"""
    for payload in (dict(certified_interior(), extra=1), {key: value for key, value in certified_interior().items() if key != "b"}):
        output = tmp_path / "report.json"
        output.write_bytes(b"prior-report\n")
        result, destination = invoke(tmp_path, payload)
        assert_input_rejected(result, destination)


def test_malformed_json_preserves_existing_report(tmp_path):
    """R3/R4：解析失败使用 E_INPUT 并保持旧报告逐字节不变。"""
    output = tmp_path / "report.json"
    output.write_bytes(b"prior-report\n")
    result, destination = invoke(tmp_path, raw="{not valid json")
    assert_input_rejected(result, destination)


def test_successful_report_is_compact_deterministic_and_newline_terminated(tmp_path):
    """R4：相同成功输入要产生键集合固定、紧凑、稳定且换行结尾的报告。"""
    payload = certified_interior()
    first, destination = invoke(tmp_path, payload)
    first_bytes = destination.read_bytes()
    second, _ = invoke(tmp_path, payload)
    assert first.returncode == second.returncode == 0
    assert first_bytes == destination.read_bytes()
    assert first_bytes.endswith(b"\n") and b", " not in first_bytes
    assert set(report(destination)) == {"active_lower", "objective", "residual_inf", "status"}
    assert not list(tmp_path.glob(".report.json.*.tmp"))


def test_failed_replacement_preserves_directory_sentinel_and_cleans_temporary_file(tmp_path):
    """R4：替换既有目录失败时必须保留其哨兵内容并清除生成的临时文件。"""
    destination = tmp_path / "report.json"
    destination.mkdir()
    sentinel = destination / "keep.bin"
    sentinel.write_bytes(b"directory-sentinel")
    source = tmp_path / "certificate.json"
    source.write_text(json.dumps(certified_interior()), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(PROGRAM), "--input", str(source), "--output", str(destination)],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert result.stderr.startswith("E_IO:")
    assert sentinel.read_bytes() == b"directory-sentinel"
    assert not list(tmp_path.glob(".report.json.*.tmp"))


def test_io_error_has_prefix_and_does_not_create_output(tmp_path):
    """R4：目标目录不存在的 I/O 错误必须以 E_IO 报告，且不制造半成品。"""
    result, destination = invoke(tmp_path, certified_interior(), output_name="missing/report.json")
    assert result.returncode != 0
    assert result.stderr.startswith("E_IO:")
    assert not destination.exists()
    assert not list(tmp_path.glob("*.tmp"))
