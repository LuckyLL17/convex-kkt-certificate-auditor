#!/usr/bin/env python3
"""Audit KKT certificates for lower-bounded convex quadratic models."""
import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path

REQUIRED = {"A", "b", "c", "lower", "x", "multipliers"}
ALLOWED = REQUIRED | {"tolerance"}

class InputError(ValueError):
    pass

def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InputError(f"{label} 必须是有限数值")
    return float(value)

def vector(value, label, length=None):
    if not isinstance(value, list):
        raise InputError(f"{label} 必须是数组")
    if length is not None and len(value) != length:
        raise InputError(f"{label} 长度不匹配")
    return [number(item, f"{label}[{index}]") for index, item in enumerate(value)]

def parse(payload):
    if not isinstance(payload, dict):
        raise InputError("顶层必须是对象")
    keys = set(payload)
    if keys - ALLOWED or REQUIRED - keys:
        raise InputError("顶层键不符合契约")
    raw_a = payload["A"]
    if not isinstance(raw_a, list) or not raw_a:
        raise InputError("A 必须是非空二维数组")
    if not all(isinstance(row, list) for row in raw_a) or not raw_a[0]:
        raise InputError("A 必须包含非空行")
    n = len(raw_a[0])
    A = [vector(row, f"A[{i}]", n) for i, row in enumerate(raw_a)]
    b = vector(payload["b"], "b", len(A))
    c = vector(payload["c"], "c", n)
    lower = vector(payload["lower"], "lower", n)
    x = vector(payload["x"], "x", n)
    multipliers = vector(payload["multipliers"], "multipliers", n)
    tolerance = number(payload.get("tolerance", 1e-8), "tolerance")
    if not 1e-12 <= tolerance <= 1e-4:
        raise InputError("tolerance 超出允许范围")
    return A, b, c, lower, x, multipliers, tolerance

def audit(payload):
    A, b, c, lower, x, mu, tol = parse(payload)
    residual = [sum(aij * xj for aij, xj in zip(row, x)) - bi for row, bi in zip(A, b)]
    gradient = [sum(A[row][col] * residual[row] for row in range(len(A))) + c[col] for col in range(len(x))]
    primal = max(0.0, *(lo - xi for lo, xi in zip(lower, x)))
    dual = max(0.0, *(-value for value in mu))
    stationary = max(abs(gi - mi) for gi, mi in zip(gradient, mu))
    complementarity = max(abs(mi * (xi - lo)) for mi, xi, lo in zip(mu, x, lower))
    violation = max(primal, dual, stationary, complementarity)
    objective = 0.5 * sum(value * value for value in residual) + sum(ci * xi for ci, xi in zip(c, x))
    if not math.isfinite(objective) or not math.isfinite(violation):
        raise InputError("计算结果不是有限数值")
    return {
        "active_lower": [index for index, (xi, lo) in enumerate(zip(x, lower)) if abs(xi - lo) <= tol],
        "objective": objective,
        "residual_inf": violation,
        "status": "CERTIFIED" if violation <= tol else "REJECTED",
    }

def atomic_write(path, report):
    target = Path(path)
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        raise OSError("输出目录不存在")
    body = json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        raw = Path(args.input).read_text(encoding="utf-8")
        payload = json.loads(raw)
        report = audit(payload)
    except (OSError, UnicodeError) as exc:
        print(f"E_IO: {exc}", file=sys.stderr)
        return 3
    except (json.JSONDecodeError, InputError) as exc:
        print(f"E_INPUT: {exc}", file=sys.stderr)
        return 2
    try:
        atomic_write(args.output, report)
    except OSError as exc:
        print(f"E_IO: {exc}", file=sys.stderr)
        return 3
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
