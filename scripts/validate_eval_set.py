#!/usr/bin/env python3
"""Validate the predictive editor evaluation set."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

EVAL_SET_PATH = Path("docs") / "evaluations" / "predictive_editor_eval_set.json"
RAW_SUFFIXES = {
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".arw",
    ".srf",
    ".sr2",
    ".raf",
    ".orf",
    ".rw2",
    ".rwl",
    ".dng",
    ".pef",
    ".ptx",
    ".3fr",
    ".fff",
    ".iiq",
    ".mrw",
    ".mef",
    ".mos",
    ".kdc",
    ".dcr",
    ".raw",
    ".srw",
    ".x3f",
    ".erf",
}


def _load_entries() -> list[dict[str, Any]]:
    payload = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit(f"Expected a JSON list in {EVAL_SET_PATH}")
    return [item for item in payload if isinstance(item, dict)]


def main() -> int:
    entries = _load_entries()
    active_entries = [entry for entry in entries if not entry.get("disabled", False)]
    disabled_entries = [entry for entry in entries if entry.get("disabled", False)]

    missing_entries: list[dict[str, Any]] = []
    valid_entries: list[dict[str, Any]] = []
    non_raw_entries: list[dict[str, Any]] = []
    active_missing_entries: list[dict[str, Any]] = []
    active_paths: list[str] = []

    for entry in entries:
        raw_path = entry.get("raw_path")
        image_id = entry.get("image_id", "<unknown>")
        disabled = bool(entry.get("disabled", False))

        if not isinstance(raw_path, str) or not raw_path:
            missing_entries.append(entry)
            if not disabled:
                active_missing_entries.append(entry)
            continue

        path = Path(raw_path)
        if not path.is_file():
            missing_entries.append(entry)
            if not disabled:
                active_missing_entries.append(entry)
            continue

        if path.suffix.lower() not in RAW_SUFFIXES:
            non_raw_entries.append(entry)

        valid_entries.append(entry)
        if not disabled:
            active_paths.append(str(path.resolve()))

    duplicate_paths = {
        path: count for path, count in Counter(active_paths).items() if count > 1
    }

    print(f"eval_set: {EVAL_SET_PATH}")
    print(f"total entries: {len(entries)}")
    print(f"active entries: {len(active_entries)}")
    print(f"valid entries: {len(valid_entries)}")
    print(f"missing entries: {len(missing_entries)}")
    print(f"disabled entries: {len(disabled_entries)}")
    print(f"non-RAW entries: {len(non_raw_entries)}")
    print(f"duplicate paths: {len(duplicate_paths)}")

    if valid_entries:
        print("valid entry ids:")
        for entry in valid_entries:
            print(f"  - {entry.get('image_id', '<unknown>')}: {entry.get('raw_path')}")

    if missing_entries:
        print("missing entry ids:")
        for entry in missing_entries:
            print(
                f"  - {entry.get('image_id', '<unknown>')}: "
                f"{entry.get('missing_reason', 'Path missing or unset')}"
            )

    if non_raw_entries:
        print("non-RAW entry ids:")
        for entry in non_raw_entries:
            print(f"  - {entry.get('image_id', '<unknown>')}: {entry.get('raw_path')}")

    if duplicate_paths:
        print("duplicate active paths:")
        for path, count in sorted(duplicate_paths.items()):
            print(f"  - {path} ({count})")

    if active_missing_entries:
        print("validation result: fail")
        for entry in active_missing_entries:
            image_id = entry.get("image_id", "<unknown>")
            raw_path = entry.get("raw_path")
            print(f"  - active entry missing source: {image_id} -> {raw_path}")
        return 1

    print("validation result: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
