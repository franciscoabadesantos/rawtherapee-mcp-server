"""Structured PP3 diff utilities for evidence-driven control analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rawtherapee_mcp.pp3_parser import PP3Profile


def _noise_reasons_for_section(section: str) -> str | None:
    """Heuristics for sections that often change from RT normalization."""
    if section == "Crop":
        return "full-image crop normalization"
    if section == "Resize":
        return "resize normalization defaults"
    if section == "LensProfile":
        return "lens profile auto-population"
    if section in {"Color appearance", "RAW"}:
        return "module default expansion after save"
    return None


def analyze_pp3_diff(before_path: Path, after_path: Path) -> dict[str, Any]:
    """Compare two PP3 files and return structured change details."""
    before_profile = PP3Profile()
    before_profile.load(before_path)
    before_data = before_profile.to_dict()

    after_profile = PP3Profile()
    after_profile.load(after_path)
    after_data = after_profile.to_dict()

    changed: list[dict[str, str]] = []
    added: list[dict[str, str]] = []
    removed: list[dict[str, str]] = []
    possible_noise: list[dict[str, str]] = []
    noise_sections_seen: set[str] = set()

    all_sections = sorted(set(before_data) | set(after_data))
    for section in all_sections:
        before_keys = before_data.get(section, {})
        after_keys = after_data.get(section, {})
        all_keys = sorted(set(before_keys) | set(after_keys))

        for key in all_keys:
            before_value = before_keys.get(key)
            after_value = after_keys.get(key)
            if before_value is None:
                added.append({"section": section, "key": key, "after": str(after_value)})
            elif after_value is None:
                removed.append({"section": section, "key": key, "before": str(before_value)})
            elif before_value != after_value:
                changed.append(
                    {
                        "section": section,
                        "key": key,
                        "before": str(before_value),
                        "after": str(after_value),
                    }
                )

        reason = _noise_reasons_for_section(section)
        section_has_diff = (
            any(item["section"] == section for item in changed)
            or any(item["section"] == section for item in added)
            or any(item["section"] == section for item in removed)
        )
        if reason and section not in noise_sections_seen and section_has_diff:
            possible_noise.append({"section": section, "reason": reason})
            noise_sections_seen.add(section)

    return {
        "before_path": str(before_path),
        "after_path": str(after_path),
        "changed": changed,
        "added": added,
        "removed": removed,
        "possible_noise": possible_noise,
    }
