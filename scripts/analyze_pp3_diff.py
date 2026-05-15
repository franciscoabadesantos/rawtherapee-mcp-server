"""CLI wrapper for structured PP3 diff analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rawtherapee_mcp.pp3_diff import analyze_pp3_diff


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two PP3 files and emit structured JSON diff output.",
    )
    parser.add_argument("before_pp3", type=Path, help="Baseline PP3 file path")
    parser.add_argument("after_pp3", type=Path, help="Modified PP3 file path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    before_path: Path = args.before_pp3
    after_path: Path = args.after_pp3

    if not before_path.is_file():
        print(json.dumps({"error": f"PP3 file not found: {before_path}"}, indent=2))
        return 1
    if not after_path.is_file():
        print(json.dumps({"error": f"PP3 file not found: {after_path}"}, indent=2))
        return 1

    diff: dict[str, Any] = analyze_pp3_diff(before_path, after_path)
    print(json.dumps(diff, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
