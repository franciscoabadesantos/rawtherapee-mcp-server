"""Manifest-backed control policy helpers for autonomous PP3 safety decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

from rawtherapee_mcp.pp3_generator import _PARAMETER_MAP


@dataclass(frozen=True)
class BlockedControl:
    """One blocked autonomous control with context for debugging."""

    control_id: str
    section: str
    key: str
    value: str
    reason: str


@dataclass(frozen=True)
class CheckedControl:
    """One checked control from a friendly autonomous parameter payload."""

    control_id: str
    section: str
    key: str
    value: str


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a candidate autonomous parameter payload."""

    allowed: bool
    blocked_controls: list[BlockedControl]
    checked_controls: list[CheckedControl]
    warnings: list[str]


def _control_id(section: str, key: str) -> str:
    return f"{section}.{key}"


def _serialize_pp3_like(value: object) -> str:
    """Serialize values using PP3-like formatting for policy matching."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        if not value:
            return "0;"
        return ";".join(str(item) for item in value) + ";"
    return str(value)


@lru_cache(maxsize=1)
def _load_manifest() -> dict[str, Any]:
    manifest_path = files("rawtherapee_mcp").joinpath("control_manifest.json")
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return {}
    return payload


def _get_control_entry(section: str, key: str) -> dict[str, Any] | None:
    manifest = _load_manifest()
    controls = manifest.get("controls", {})
    if not isinstance(controls, dict):
        return None
    entry = controls.get(_control_id(section, key))
    return entry if isinstance(entry, dict) else None


def get_control_risk(section: str, key: str) -> list[str]:
    """Return risk annotations for a PP3 control from the manifest."""
    entry = _get_control_entry(section, key)
    if entry is None:
        return ["Unknown control: manual-only until evidence is captured."]
    risks = entry.get("risks", [])
    if isinstance(risks, list) and all(isinstance(risk, str) for risk in risks):
        return list(risks)
    return []


def is_control_allowed_autonomous(section: str, key: str, value: object | None = None) -> bool:
    """Check whether one PP3 control is currently allowed for autonomous use."""
    entry = _get_control_entry(section, key)
    if entry is None:
        return False

    policy = entry.get("autonomous_allowed")
    if policy is True:
        return True
    if policy is False:
        return False
    if policy == "approved_curve_only":
        approved_values = entry.get("approved_values", [])
        if not isinstance(approved_values, list):
            return False
        serialized_value = _serialize_pp3_like(value)
        return serialized_value in approved_values
    return False


def validate_autonomous_parameters(parameters: dict[str, Any]) -> ValidationResult:
    """Validate friendly autonomous parameters against manifest policy."""
    blocked_controls: list[BlockedControl] = []
    checked_controls: list[CheckedControl] = []
    warnings: list[str] = []

    for group_name, group_values in parameters.items():
        if not isinstance(group_values, dict):
            warnings.append(f"Skipped non-dict parameter group: {group_name}")
            continue

        group_map = _PARAMETER_MAP.get(group_name.lower())
        if group_map is None:
            blocked_controls.append(
                BlockedControl(
                    control_id=f"{group_name}.*",
                    section=group_name,
                    key="*",
                    value="",
                    reason="Unknown parameter group: manual-only by default",
                )
            )
            continue

        for key_name, value in group_values.items():
            mapped = group_map.get(key_name.lower())
            serialized_value = _serialize_pp3_like(value)
            if mapped is None:
                blocked_controls.append(
                    BlockedControl(
                        control_id=f"{group_name}.{key_name}",
                        section=group_name,
                        key=key_name,
                        value=serialized_value,
                        reason="Unknown control key: manual-only by default",
                    )
                )
                continue

            section, pp3_key = mapped
            control_id = _control_id(section, pp3_key)
            checked_controls.append(
                CheckedControl(
                    control_id=control_id,
                    section=section,
                    key=pp3_key,
                    value=serialized_value,
                )
            )
            if not is_control_allowed_autonomous(section, pp3_key, value):
                entry = _get_control_entry(section, pp3_key)
                if entry is None:
                    reason = "Not in manifest: manual-only by default"
                else:
                    policy = entry.get("autonomous_allowed")
                    if policy == "approved_curve_only":
                        reason = "Value is not in approved curve list"
                    else:
                        reason = "Control is blocked for autonomous editing"
                blocked_controls.append(
                    BlockedControl(
                        control_id=control_id,
                        section=section,
                        key=pp3_key,
                        value=serialized_value,
                        reason=reason,
                    )
                )

    return ValidationResult(
        allowed=not blocked_controls,
        blocked_controls=blocked_controls,
        checked_controls=checked_controls,
        warnings=warnings,
    )
