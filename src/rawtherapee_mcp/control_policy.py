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
def load_manifest() -> dict[str, Any]:
    manifest_path = files("rawtherapee_mcp").joinpath("control_manifest.json")
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return {}
    return payload


def _get_control_entry(section: str, key: str) -> dict[str, Any] | None:
    manifest = load_manifest()
    controls = manifest.get("controls", {})
    if not isinstance(controls, dict):
        return None
    entry = controls.get(_control_id(section, key))
    return entry if isinstance(entry, dict) else None


def get_approved_curve_registry() -> dict[str, dict[str, Any]]:
    """Return approved autonomous curve presets keyed by curve id."""
    manifest = load_manifest()
    registry = manifest.get("approved_curves", {})
    if not isinstance(registry, dict):
        return {}
    return {key: value for key, value in registry.items() if isinstance(key, str) and isinstance(value, dict)}


def get_approved_curve(curve_id: str) -> dict[str, Any] | None:
    """Return one approved curve descriptor by id."""
    return get_approved_curve_registry().get(curve_id)


def find_approved_curve(section: str, key: str, value: object) -> dict[str, Any] | None:
    """Resolve approved-curve metadata for one exact PP3 section/key/value triple."""
    serialized_value = _serialize_pp3_like(value)
    for curve in get_approved_curve_registry().values():
        fields = curve.get("pp3_fields")
        if isinstance(fields, dict):
            expected = fields.get(_control_id(section, key))
            if expected is not None and _serialize_pp3_like(expected) == serialized_value:
                return curve
        if (
            str(curve.get("pp3_section", "")) == section
            and str(curve.get("pp3_key", "")) == key
            and str(curve.get("curve_string", "")) == serialized_value
        ):
            return curve
    return None


def _coerce_numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _is_expected_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.lower() in {"true", "false"}
    return False


def _is_expected_integer(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return False
        return parsed.is_integer()
    return False


def _value_within_range(entry: dict[str, Any], value: object) -> bool:
    suggested_range = entry.get("suggested_autonomous_range")
    if not isinstance(suggested_range, list) or len(suggested_range) != 2:
        return True

    numeric_value = _coerce_numeric(value)
    if numeric_value is None:
        return False

    minimum_raw = suggested_range[0]
    maximum_raw = suggested_range[1]
    minimum = _coerce_numeric(minimum_raw)
    maximum = _coerce_numeric(maximum_raw)
    if minimum is not None and numeric_value < minimum:
        return False
    if maximum is not None and numeric_value > maximum:
        return False
    return True


def _is_expected_value_type(entry: dict[str, Any], value: object) -> bool:
    value_type = entry.get("value_type")
    if value_type == "boolean":
        return _is_expected_boolean(value)
    if value_type == "integer":
        return _is_expected_integer(value)
    if value_type == "number":
        return _coerce_numeric(value) is not None
    return True


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
    if value is not None and not _is_expected_value_type(entry, value):
        return False
    if policy is True:
        return value is None or _value_within_range(entry, value)
    if policy is False:
        return False
    if policy in {"approved_curve_only", "approved_values_only"}:
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
                    if not _is_expected_value_type(entry, value):
                        reason = f"Invalid value type for control (expected {entry.get('value_type')})"
                    elif policy in {"approved_curve_only", "approved_values_only"}:
                        reason = "Value is not in approved curve list"
                    elif policy is True and not _value_within_range(entry, value):
                        reason = "Value is outside suggested autonomous range"
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


def build_manifest_report() -> dict[str, Any]:
    """Build an audit-friendly summary of manifest readiness."""
    manifest = load_manifest()
    controls = manifest.get("controls", {})
    if not isinstance(controls, dict):
        controls = {}

    allowed: list[str] = []
    blocked: list[str] = []
    pending_evidence: list[str] = []
    approved_values: dict[str, list[str]] = {}

    for control_id in sorted(controls):
        entry = controls.get(control_id)
        if not isinstance(entry, dict):
            continue

        policy = entry.get("autonomous_allowed")
        if policy is True:
            allowed.append(control_id)
        else:
            blocked.append(control_id)

        if entry.get("pending_evidence") is True:
            pending_evidence.append(control_id)

        values = entry.get("approved_values")
        if isinstance(values, list) and values:
            normalized = [value for value in values if isinstance(value, str)]
            approved_values[control_id] = normalized

    return {
        "rawtherapee_versions": manifest.get("rawtherapee_versions", {}),
        "unknown_default_policy": manifest.get("default_policy", {}),
        "allowed_autonomous_controls": allowed,
        "blocked_controls": blocked,
        "pending_evidence_controls": pending_evidence,
        "approved_curve_values": approved_values,
    }


def build_agent_manifest_summary() -> dict[str, Any]:
    """Build a compact agent-facing summary of autonomous-safe manifest controls."""
    manifest = load_manifest()
    controls = manifest.get("controls", {})
    if not isinstance(controls, dict):
        controls = {}

    approved_curves = get_approved_curve_registry()
    hidden_support_controls = {"Exposure.CurveMode", "Exposure.Curve2"}
    entries: list[dict[str, Any]] = []

    for control_id in sorted(controls):
        entry = controls.get(control_id)
        if not isinstance(entry, dict):
            continue
        if control_id in hidden_support_controls:
            continue

        policy = entry.get("autonomous_allowed")
        if policy not in {True, "approved_curve_only", "approved_values_only"}:
            continue

        summary_entry: dict[str, Any] = {
            "control_id": control_id,
            "ui_name": str(entry.get("ui_name", control_id)),
            "value_type": str(entry.get("value_type", "unknown")),
            "expected_effect": str(entry.get("expected_effect", "")),
            "risks": [str(risk) for risk in entry.get("risks", []) if isinstance(risk, str)],
            "confidence": str(entry.get("confidence", "unknown")),
            "pending_evidence": bool(entry.get("pending_evidence", False)),
        }

        if policy is True:
            suggested_range = entry.get("suggested_autonomous_range")
            summary_entry["allowed_range"] = suggested_range if isinstance(suggested_range, list) else None
        else:
            summary_entry["policy"] = str(policy)
            approved_values: list[dict[str, Any]] = []
            for curve in approved_curves.values():
                fields = curve.get("pp3_fields")
                if not isinstance(fields, dict) or control_id not in fields:
                    continue
                approved_values.append(
                    {
                        "id": str(curve.get("id", "")),
                        "intended_effect": str(curve.get("intended_effect", "")),
                        "risk_notes": [str(note) for note in curve.get("risk_notes", []) if isinstance(note, str)],
                    }
                )
            summary_entry["approved_values"] = approved_values

        entries.append(summary_entry)

    return {
        "planning_contract": {
            "selection_rule": "Select only from the listed controls. Unknown or hidden controls are blocked.",
            "vision_rule": (
                "A safe but visually irrelevant edit is a failure. A conservative edit that does not execute the "
                "user's vision is a failure."
            ),
            "quality_rule": (
                "Avoiding artifacts is necessary but not sufficient. Use the manifest controls to serve the visual goal."
            ),
            "capability_rule": "If the available controls cannot execute the vision, say so explicitly.",
            "pending_evidence_rule": (
                "Controls marked pending_evidence=true are available but less proven and should be used conservatively."
            ),
        },
        "controls": entries,
    }
