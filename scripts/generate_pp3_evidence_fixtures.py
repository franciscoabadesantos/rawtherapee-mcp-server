"""Generate PP3 evidence fixtures for calibrated controls in control_manifest.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rawtherapee_mcp.control_policy import load_manifest
from rawtherapee_mcp.pp3_diff import analyze_pp3_diff
from rawtherapee_mcp.pp3_parser import PP3Profile

BASE_FIXTURE = Path("tests/fixtures/sample.pp3")
OUTPUT_ROOT = Path("docs/reference/pp3_evidence")


def _control_value_candidates(entry: dict[str, Any]) -> dict[str, str]:
    observed = entry.get("observed_ui_values", {})
    if not isinstance(observed, dict):
        observed = {}

    approved_values = entry.get("approved_values", [])
    if not isinstance(approved_values, list):
        approved_values = []

    value_type = entry.get("value_type")
    default_value = observed.get("default", 0)
    enabled_value = observed.get("enabled")

    if value_type == "boolean":
        enabled_fallback = True if enabled_value is None else enabled_value
        return {
            "enabled": str(enabled_fallback).lower(),
            "low": str(default_value).lower(),
            "medium": str(enabled_fallback).lower(),
            "high": str(enabled_fallback).lower(),
        }

    if approved_values:
        first = approved_values[0]
        return {"enabled": str(first), "low": str(first), "medium": str(first), "high": str(first)}

    low = observed.get("low", default_value)
    medium = observed.get("medium", low)
    high = observed.get("high", medium)
    enabled = enabled_value if enabled_value is not None else medium
    return {"enabled": str(enabled), "low": str(low), "medium": str(medium), "high": str(high)}


def _write_variant(base: PP3Profile, section: str, key: str, value: str, out_path: Path) -> None:
    variant = base.copy()
    variant.set(section, key, value)
    variant.save(out_path)


def main() -> int:
    if not BASE_FIXTURE.is_file():
        raise SystemExit(f"Base fixture missing: {BASE_FIXTURE}")

    manifest = load_manifest()
    controls = manifest.get("controls", {})
    if not isinstance(controls, dict):
        raise SystemExit("Invalid manifest controls payload")

    base_profile = PP3Profile()
    base_profile.load(BASE_FIXTURE)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    for control_id in sorted(controls):
        entry = controls[control_id]
        if not isinstance(entry, dict):
            continue
        section = entry.get("pp3_section")
        key = entry.get("pp3_key")
        if not isinstance(section, str) or not isinstance(key, str):
            continue

        control_dir = OUTPUT_ROOT / control_id
        control_dir.mkdir(parents=True, exist_ok=True)

        base_path = control_dir / "base_settled.pp3"
        base_profile.save(base_path)

        values = _control_value_candidates(entry)
        variant_paths = {
            "control_enabled": control_dir / "control_enabled.pp3",
            "control_low": control_dir / "control_low.pp3",
            "control_medium": control_dir / "control_medium.pp3",
            "control_high": control_dir / "control_high.pp3",
        }

        _write_variant(base_profile, section, key, values["enabled"], variant_paths["control_enabled"])
        _write_variant(base_profile, section, key, values["low"], variant_paths["control_low"])
        _write_variant(base_profile, section, key, values["medium"], variant_paths["control_medium"])
        _write_variant(base_profile, section, key, values["high"], variant_paths["control_high"])

        diffs = {
            name: analyze_pp3_diff(base_path, path)
            for name, path in variant_paths.items()
        }
        (control_dir / "diff.json").write_text(json.dumps(diffs, indent=2), encoding="utf-8")

        notes = [
            f"# {control_id}",
            "",
            f"- section/key: `{section}.{key}`",
            f"- autonomous_allowed: `{entry.get('autonomous_allowed')}`",
            f"- confidence: `{entry.get('confidence', 'unknown')}`",
            f"- pending_evidence: `{entry.get('pending_evidence', False)}`",
            f"- expected_effect: {entry.get('expected_effect', '')}",
            f"- risks: {entry.get('risks', [])}",
            "",
            "Evidence sources:",
        ]
        evidence = entry.get("evidence", [])
        if isinstance(evidence, list):
            notes.extend(f"- {item}" for item in evidence if isinstance(item, str))
        (control_dir / "notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
