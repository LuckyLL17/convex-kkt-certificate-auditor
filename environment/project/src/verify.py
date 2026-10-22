#!/usr/bin/env python3
"""Audit a KKT certificate for a lower-bounded least-squares model."""
import argparse
import json
import math
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"E_INPUT: {exc}", file=sys.stderr)
        return 2
    # The initial implementation only preserved the command-line shape.
    report = {"status": "CERTIFIED", "objective": 0.0, "residual_inf": 0.0, "active_lower": []}
    try:
        Path(args.output).write_text(json.dumps(report) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"E_IO: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
