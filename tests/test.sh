#!/bin/sh
set -eu
REWARD_PATH="${TEST_REWARD_PATH:-/logs/verifier/reward.txt}"
mkdir -p "$(dirname "$REWARD_PATH")"
APP_DIR="${APP_DIR:-/app}"
TEST_ROOT="$(dirname "$0")"
printf '0.000\n' > "$REWARD_PATH"
PYTEST_HOME="${PYTEST_HOME:-/tmp/convex-kkt-pytest}"
rm -rf "$PYTEST_HOME"
mkdir -p "$PYTEST_HOME"
python3 -m pip install --disable-pip-version-check --no-index --find-links "$TEST_ROOT/wheels" --require-hashes --target "$PYTEST_HOME" -r "$TEST_ROOT/requirements-verifier.txt"
export APP_DIR PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PYTEST_HOME${PYTHONPATH:+:$PYTHONPATH}"
RESULTS="$(mktemp)"
cleanup() { rm -f "$RESULTS"; }
trap cleanup EXIT HUP INT TERM
set +e
python3 -m pytest -p no:cacheprovider --collect-only -q "$(dirname "$0")/test_verify.py"
COLLECT_STATUS=$?
if [ "$COLLECT_STATUS" -ne 0 ]; then
  exit "$COLLECT_STATUS"
fi
python3 -m pytest -p no:cacheprovider -q "$(dirname "$0")/test_verify.py" --junitxml="$RESULTS"
STATUS=$?
set -e
python3 - "$RESULTS" "$REWARD_PATH" "$STATUS" <<'PY'
import math
import sys
import xml.etree.ElementTree as ET
results_path, reward_path, status = sys.argv[1], sys.argv[2], int(sys.argv[3])
groups = {
    "core": (0.45, {
        "test_certifies_interior_stationary_certificate", "test_certifies_active_constraint_with_positive_multiplier",
        "test_rejects_primal_violation_and_reports_maximum_residual", "test_rejects_stationarity_sign_or_gradient_mismatch",
        "test_rejects_nonzero_complementarity"}),
    "boundary": (0.20, {"test_marks_near_lower_coordinate_active_under_public_tolerance", "test_rejects_out_of_range_tolerance_without_replacing_report"}),
    "input": (0.20, {"test_rejects_inconsistent_matrix_and_vector_dimensions", "test_rejects_boolean_and_nonfinite_values", "test_rejects_missing_or_extra_top_level_keys", "test_malformed_json_preserves_existing_report"}),
    "output": (0.15, {"test_successful_report_is_compact_deterministic_and_newline_terminated", "test_failed_replacement_preserves_directory_sentinel_and_cleans_temporary_file", "test_io_error_has_prefix_and_does_not_create_output"}),
}
try:
    root = ET.parse(results_path).getroot()
    failed = {case.attrib.get("name") for case in root.iter("testcase") if any(child.tag in {"failure", "error", "skipped"} for child in case)}
    observed = {case.attrib.get("name") for case in root.iter("testcase")}
    expected = set().union(*(names for _, names in groups.values()))
    if status != 0 and not observed or observed != expected:
        raise RuntimeError("测试收集或执行不完整")
    reward = sum(weight * (len(names - failed) / len(names)) for weight, names in groups.values())
    if not math.isfinite(reward) or not 0 <= reward <= 1:
        raise RuntimeError("奖励非法")
except Exception:
    reward = 0.0
with open(reward_path, "w", encoding="ascii", newline="\n") as handle:
    handle.write(f"{reward:.3f}\n")
PY
exit "$STATUS"
