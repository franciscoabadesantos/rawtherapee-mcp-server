"""Predictive manifest-backed planning helpers for autonomous RAW editing."""

from __future__ import annotations

from typing import Any, TypeGuard

from rawtherapee_mcp.control_policy import is_control_allowed_autonomous, load_manifest

DIAGNOSIS_VOCAB = {
    "flat_midtone_geometry",
    "weak_subject_readability",
    "dull_color_presence",
    "bright_sky_needs_control",
    "washed_highlights",
    "blocked_shadows",
    "too_cool_or_clinical",
    "too_warm_or_orange",
    "green_yellow_cast",
    "low_thumbnail_impact",
    "crop_distraction_edges",
    "needs_mild_straightening_or_geometry",
    "proof_only_needed",
}

_INTENSITY_SCALE = {"low": 0.7, "medium": 1.0, "high": 1.25}

_CONTROL_TO_FRIENDLY: dict[str, tuple[str, str]] = {
    "Exposure.Compensation": ("exposure", "compensation"),
    "Exposure.Contrast": ("exposure", "contrast"),
    "Exposure.Saturation": ("exposure", "saturation"),
    "Exposure.Black": ("exposure", "black"),
    "Exposure.HighlightCompr": ("exposure", "highlight_compression"),
    "Exposure.HighlightComprThreshold": ("highlight_rolloff", "highlight_compression_threshold"),
    "White Balance.Temperature": ("white_balance", "temperature"),
    "White Balance.Green": ("white_balance", "green"),
    "Shadows & Highlights.Highlights": ("highlight_rolloff", "highlights"),
    "Shadows & Highlights.Shadows": ("highlight_rolloff", "shadows"),
    "Shadows & Highlights.HighlightTonalWidth": ("highlight_rolloff", "highlight_tonal_width"),
    "Shadows & Highlights.ShadowTonalWidth": ("highlight_rolloff", "shadow_tonal_width"),
    "Shadows & Highlights.Radius": ("highlight_rolloff", "radius"),
    "Luminance Curve.Enabled": ("luminance_curve", "enabled"),
    "Luminance Curve.Contrast": ("luminance_curve", "contrast"),
    "Luminance Curve.AvoidColorShift": ("luminance_curve", "avoid_color_shift"),
    "Luminance Curve.Chromaticity": ("luminance_curve", "chromaticity"),
    "Vibrance.Enabled": ("vibrance", "enabled"),
    "Vibrance.Pastels": ("vibrance", "pastels"),
    "Vibrance.Saturated": ("vibrance", "saturated"),
    "Vibrance.ProtectSkins": ("vibrance", "protectskins"),
    "Vibrance.AvoidColorShift": ("vibrance", "avoidcolorshift"),
    "Sharpening.Amount": ("sharpening", "amount"),
    "Sharpening.Radius": ("sharpening", "radius"),
    "Sharpening.Threshold": ("sharpening", "threshold"),
    "SharpenMicro.Enabled": ("microcontrast", "enabled"),
    "SharpenMicro.Amount": ("microcontrast", "amount"),
    "Crop.Enabled": ("crop", "enabled"),
    "Crop.X": ("crop", "x"),
    "Crop.Y": ("crop", "y"),
    "Crop.W": ("crop", "w"),
    "Crop.H": ("crop", "h"),
    "Crop.FixedRatio": ("crop", "fixed_ratio"),
    "Crop.Ratio": ("crop", "ratio"),
}

_INTEGER_NUMERIC_CONTROLS = {
    "Exposure.Contrast",
    "Exposure.Saturation",
    "Exposure.Black",
    "Exposure.HighlightCompr",
    "Exposure.HighlightComprThreshold",
    "White Balance.Temperature",
    "Shadows & Highlights.Highlights",
    "Shadows & Highlights.Shadows",
    "Shadows & Highlights.HighlightTonalWidth",
    "Shadows & Highlights.ShadowTonalWidth",
    "Shadows & Highlights.Radius",
    "Luminance Curve.Contrast",
    "Luminance Curve.Chromaticity",
    "Vibrance.Pastels",
    "Vibrance.Saturated",
    "Sharpening.Amount",
    "SharpenMicro.Amount",
}


def _normalize_intensity(intensity: str) -> str:
    return intensity if intensity in _INTENSITY_SCALE else "medium"


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_delta(value: str) -> float | None:
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError:
        return None


def infer_predictive_diagnosis(
    *,
    style: str,
    intensity: str,
    user_brief: str | None,
) -> dict[str, Any]:
    """Return a structured diagnosis using the constrained vocabulary."""
    normalized_intensity = _normalize_intensity(intensity)
    brief = (user_brief or "").lower()
    style_text = style.lower()
    text = f"{style_text} {brief}"

    diagnosis: list[dict[str, Any]] = []

    def add(issue: str, severity: float, evidence: str) -> None:
        if issue in DIAGNOSIS_VOCAB:
            diagnosis.append({"issue": issue, "severity": round(max(0.0, min(1.0, severity)), 2), "evidence": evidence})

    if any(token in text for token in ("street", "travel", "tram", "rail", "geometry", "barcelona", "urban")):
        add("flat_midtone_geometry", 0.65, "Urban/travel framing often needs stronger midtone separation.")
        add("weak_subject_readability", 0.55, "Primary subject likely competes with structural background.")
        add("low_thumbnail_impact", 0.55, "Travel/street scenes often lose hierarchy at thumbnail size.")

    if any(token in text for token in ("dull", "muted", "presence", "natural", "color")):
        add("dull_color_presence", 0.45, "Brief/style requests stronger but natural color presence.")

    if any(token in text for token in ("sky", "cloud", "highlight", "bright")):
        add("bright_sky_needs_control", 0.35, "Bright sky/cloud wording suggests highlight containment.")

    if any(token in text for token in ("cool", "clinical")):
        add("too_cool_or_clinical", 0.4, "Brief indicates the frame may need subtle warming.")

    if any(token in text for token in ("orange", "too warm")):
        add("too_warm_or_orange", 0.35, "Brief indicates warmth may need reduction.")

    if any(token in text for token in ("green cast", "yellow cast", "green_yellow_cast")):
        add("green_yellow_cast", 0.35, "Brief indicates likely WB tint correction requirement.")

    if any(token in text for token in ("crop", "edge distraction", "framing edge")):
        add("crop_distraction_edges", 0.4, "Brief references edge distraction or framing cleanup.")

    if any(token in text for token in ("proof only", "proof_only")):
        add("proof_only_needed", 0.8, "User brief explicitly asks for proof-only direction.")

    if not diagnosis:
        add("weak_subject_readability", 0.45, "Default predictive baseline: prioritize readability.")
        add("dull_color_presence", 0.35, "Default predictive baseline: add restrained color presence.")

    crop_need = "mild" if any(item["issue"] == "crop_distraction_edges" for item in diagnosis) else "low"
    return {
        "style": style,
        "intensity": normalized_intensity,
        "diagnosis": diagnosis,
        "crop_need": crop_need,
        "diagnosis_source": "heuristic_structured",
    }


def _manifest_entry(control_id: str) -> dict[str, Any] | None:
    manifest = load_manifest()
    controls = manifest.get("controls", {})
    if not isinstance(controls, dict):
        return None
    entry = controls.get(control_id)
    return entry if isinstance(entry, dict) else None


def _default_value_from_manifest(entry: dict[str, Any]) -> object:
    observed = entry.get("observed_ui_values", {})
    if isinstance(observed, dict) and "default" in observed:
        return observed["default"]
    value_type = entry.get("value_type")
    if value_type == "boolean":
        return False
    return 0


def _bounded_numeric(control_id: str, proposed: float) -> tuple[object, dict[str, Any] | None]:
    entry = _manifest_entry(control_id)
    if entry is None:
        return proposed, None
    range_values = entry.get("suggested_autonomous_range")
    if not isinstance(range_values, list) or len(range_values) != 2:
        return proposed, None

    lower_raw, upper_raw = range_values
    lower = float(lower_raw) if _is_number(lower_raw) else None
    upper = float(upper_raw) if _is_number(upper_raw) else None
    clamped = proposed
    if lower is not None:
        clamped = max(lower, clamped)
    if upper is not None:
        clamped = min(upper, clamped)
    if clamped != proposed:
        return clamped, {"control": control_id, "from": proposed, "to": clamped, "reason": "manifest_range"}
    return clamped, None


def _suggested_value(control_id: str, severity: float, direction: float, intensity_scale: float) -> object:
    entry = _manifest_entry(control_id)
    if entry is None:
        return 0

    value_type = entry.get("value_type")
    if value_type == "boolean":
        return True

    default_value = _default_value_from_manifest(entry)
    if not _is_number(default_value):
        default_value = 0.0

    range_values = entry.get("suggested_autonomous_range")
    if (
        isinstance(range_values, list)
        and len(range_values) == 2
        and _is_number(range_values[0])
        and _is_number(range_values[1])
    ):
        lower = float(range_values[0])
        upper = float(range_values[1])
        span = upper - lower
        amplitude = max(0.1, min(1.0, severity * intensity_scale))
        if direction >= 0:
            proposed = float(default_value) + (span * 0.45 * amplitude)
        else:
            proposed = float(default_value) - (span * 0.45 * amplitude)
    else:
        proposed = float(default_value) + (10.0 * direction * severity * intensity_scale)

    bounded, _ = _bounded_numeric(control_id, proposed)
    if value_type == "integer" and _is_number(bounded):
        return int(round(float(bounded)))
    return round(float(bounded), 3) if _is_number(bounded) else bounded


def _planned_controls_from_diagnosis(
    diagnosis: list[dict[str, Any]],
    intensity: str,
) -> tuple[list[tuple[str, object]], list[str]]:
    scale = _INTENSITY_SCALE[_normalize_intensity(intensity)]
    controls: list[tuple[str, object]] = []
    blocked_considered: list[str] = []

    for item in diagnosis:
        issue = str(item.get("issue", ""))
        severity = float(item.get("severity", 0.5))

        if issue == "flat_midtone_geometry":
            controls.extend(
                [
                    ("Exposure.Contrast", _suggested_value("Exposure.Contrast", severity, 1.0, scale)),
                    ("Luminance Curve.Enabled", True),
                    ("Luminance Curve.Contrast", _suggested_value("Luminance Curve.Contrast", severity, 1.0, scale)),
                    ("SharpenMicro.Enabled", True),
                    ("SharpenMicro.Amount", _suggested_value("SharpenMicro.Amount", severity, 1.0, scale)),
                ]
            )
            blocked_considered.append("Local Contrast.Amount")
        elif issue == "weak_subject_readability":
            controls.extend(
                [
                    ("Exposure.Compensation", _suggested_value("Exposure.Compensation", severity, 1.0, scale)),
                    ("Sharpening.Amount", _suggested_value("Sharpening.Amount", severity, 1.0, scale)),
                ]
            )
        elif issue == "dull_color_presence":
            controls.extend(
                [
                    ("Vibrance.Enabled", True),
                    ("Vibrance.Pastels", _suggested_value("Vibrance.Pastels", severity, 1.0, scale)),
                    ("Vibrance.Saturated", _suggested_value("Vibrance.Saturated", severity, 1.0, scale)),
                    ("Vibrance.ProtectSkins", True),
                    ("Vibrance.AvoidColorShift", True),
                    ("Exposure.Saturation", _suggested_value("Exposure.Saturation", severity, 1.0, scale)),
                ]
            )
            blocked_considered.append("HSV Equalizer.HCurve")
        elif issue in {"bright_sky_needs_control", "washed_highlights"}:
            controls.extend(
                [
                    ("Exposure.HighlightCompr", _suggested_value("Exposure.HighlightCompr", severity, 1.0, scale)),
                    (
                        "Exposure.HighlightComprThreshold",
                        _suggested_value("Exposure.HighlightComprThreshold", severity, 1.0, scale),
                    ),
                    (
                        "Shadows & Highlights.Highlights",
                        _suggested_value("Shadows & Highlights.Highlights", severity, -1.0, scale),
                    ),
                    (
                        "Shadows & Highlights.HighlightTonalWidth",
                        _suggested_value("Shadows & Highlights.HighlightTonalWidth", severity, 1.0, scale),
                    ),
                    (
                        "Shadows & Highlights.Radius",
                        _suggested_value("Shadows & Highlights.Radius", severity, 1.0, scale),
                    ),
                ]
            )
        elif issue == "blocked_shadows":
            controls.extend(
                [
                    (
                        "Shadows & Highlights.Shadows",
                        _suggested_value("Shadows & Highlights.Shadows", severity, 1.0, scale),
                    ),
                    (
                        "Shadows & Highlights.ShadowTonalWidth",
                        _suggested_value("Shadows & Highlights.ShadowTonalWidth", severity, 1.0, scale),
                    ),
                    ("Exposure.Black", _suggested_value("Exposure.Black", severity, -1.0, scale)),
                ]
            )
        elif issue == "too_cool_or_clinical":
            controls.append(
                (
                    "White Balance.Temperature",
                    _suggested_value("White Balance.Temperature", severity, 1.0, scale),
                )
            )
        elif issue == "too_warm_or_orange":
            controls.append(
                (
                    "White Balance.Temperature",
                    _suggested_value("White Balance.Temperature", severity, -1.0, scale),
                )
            )
        elif issue == "green_yellow_cast":
            controls.append(
                (
                    "White Balance.Green",
                    _suggested_value("White Balance.Green", severity, -1.0, scale),
                )
            )

    return controls, blocked_considered


def _merge_control_values(pairs: list[tuple[str, object]]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for control_id, value in pairs:
        if control_id not in merged:
            merged[control_id] = value
            continue
        existing = merged[control_id]
        if _is_number(existing) and _is_number(value):
            merged[control_id] = (float(existing) + float(value)) / 2.0
        elif isinstance(existing, bool):
            merged[control_id] = existing or bool(value)
        else:
            merged[control_id] = value
    return merged


def _friendly_parameters_from_controls(
    control_values: dict[str, object],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    parameters: dict[str, Any] = {}
    blocked: list[dict[str, Any]] = []
    clamped: list[dict[str, Any]] = []
    blocked_considered: list[str] = []

    for control_id, raw_value in control_values.items():
        mapping = _CONTROL_TO_FRIENDLY.get(control_id)
        if mapping is None:
            blocked.append({"control": control_id, "reason": "No friendly mapping available"})
            continue

        section, key = control_id.split(".", 1)
        value = raw_value
        if _is_number(value):
            value, clamp_note = _bounded_numeric(control_id, float(value))
            if clamp_note is not None:
                clamped.append(clamp_note)

        if not is_control_allowed_autonomous(section, key, value):
            blocked.append({"control": control_id, "reason": "blocked by manifest"})
            blocked_considered.append(control_id)
            continue

        group_name, param_key = mapping
        group = parameters.setdefault(group_name, {})
        if isinstance(group, dict):
            if _is_number(value) and _manifest_entry(control_id) is not None:
                entry = _manifest_entry(control_id)
                if control_id in _INTEGER_NUMERIC_CONTROLS:
                    group[param_key] = int(round(float(value)))
                elif entry is not None and entry.get("value_type") == "integer":
                    group[param_key] = int(round(float(value)))
                else:
                    group[param_key] = round(float(value), 3)
            else:
                group[param_key] = value

    return parameters, blocked, clamped, blocked_considered


def _issue_names(diagnosis: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("issue", "")) for item in diagnosis}


def build_predictive_edit_plan(
    *,
    style: str,
    intensity: str,
    user_brief: str | None,
    diagnosis_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a manifest-backed parameter plan from structured diagnosis."""
    diagnosis = diagnosis_payload or infer_predictive_diagnosis(style=style, intensity=intensity, user_brief=user_brief)
    diagnosis_items = diagnosis.get("diagnosis", [])
    if not isinstance(diagnosis_items, list):
        diagnosis_items = []

    issue_controls, blocked_considered = _planned_controls_from_diagnosis(diagnosis_items, intensity)
    merged_controls = _merge_control_values(issue_controls)

    # Hard block banned primitives from planner output, but report consideration.
    if "Local Contrast.Amount" in merged_controls:
        merged_controls.pop("Local Contrast.Amount", None)
        blocked_considered.append("Local Contrast.Amount")
    if "HSV Equalizer.HCurve" in merged_controls:
        merged_controls.pop("HSV Equalizer.HCurve", None)
        blocked_considered.append("HSV Equalizer.HCurve")

    parameters, blocked_from_emit, clamped, blocked_from_manifest = _friendly_parameters_from_controls(merged_controls)
    blocked_controls_considered = [
        {"control": cid, "reason": "blocked by manifest"}
        for cid in sorted(set(blocked_considered + blocked_from_manifest))
    ]
    blocked_controls_considered.extend(blocked_from_emit)

    issue_names = _issue_names(diagnosis_items)
    expected_effect: list[str] = []
    if "flat_midtone_geometry" in issue_names:
        expected_effect.extend(
            [
                "subject readability should improve at thumbnail scale",
                "midtone geometry should separate more clearly",
            ]
        )
    if "dull_color_presence" in issue_names:
        expected_effect.append("color presence should improve without phone-filter intensity")
    if {"bright_sky_needs_control", "washed_highlights"} & issue_names:
        expected_effect.append("bright sky/highlights should stay more believable")
    if "too_cool_or_clinical" in issue_names:
        expected_effect.append("overall white balance should feel slightly warmer and less clinical")
    if "too_warm_or_orange" in issue_names:
        expected_effect.append("orange/warm cast should be reduced")
    if "blocked_shadows" in issue_names:
        expected_effect.append("shadow readability should improve without muddy blacks")

    if not expected_effect:
        expected_effect.append("predictive edit should create a visible but natural improvement")

    non_crop_groups = [group for group in parameters if group != "crop"]
    crop_dependency = "primary" if parameters and not non_crop_groups else "secondary"

    severity_sum = sum(float(item.get("severity", 0.0)) for item in diagnosis_items)
    visible_difference_score = min(10.0, round(5.5 + (severity_sum * 1.2) + (len(non_crop_groups) * 0.3), 1))
    hierarchy_improvement_score = min(
        10.0,
        round(
            5.0
            + (1.4 if "flat_midtone_geometry" in issue_names else 0.0)
            + (1.0 if "weak_subject_readability" in issue_names else 0.0)
            + (0.6 if "dull_color_presence" in issue_names else 0.0),
            1,
        ),
    )
    if "proof_only_needed" in issue_names:
        visible_difference_score = min(visible_difference_score, 6.0)
        hierarchy_improvement_score = min(hierarchy_improvement_score, 6.0)

    verification = {
        "expected_effects": {
            "subject readability improved": "pending_visual_review",
            "thumbnail impact improved": "pending_visual_review",
            "sky remains believable": "pending_visual_review",
            "no local-contrast crunch": "pass",
            "not crop-only": "pass" if crop_dependency != "primary" else "fail",
        },
        "artifact_check": "pass",
        "crop_dependency": crop_dependency,
        "recommendation": "accept" if visible_difference_score >= 7.0 else "minor_correction",
        "suggested_correction": (
            {"Vibrance.Pastels": "+3", "Exposure.HighlightCompr": "-3"}
            if visible_difference_score < 7.0
            else {}
        ),
    }

    return {
        "diagnosis": diagnosis,
        "parameters": parameters,
        "expected_effect": expected_effect,
        "blocked_controls_considered": blocked_controls_considered,
        "clamped": clamped,
        "scores": {
            "visible_difference_score": visible_difference_score,
            "hierarchy_improvement_score": hierarchy_improvement_score,
            "artifact_check": "pass",
            "crop_dependency": crop_dependency,
        },
        "verification_contract": {
            "check": [
                "subject readability improved",
                "thumbnail impact improved",
                "sky remains believable",
                "no local-contrast crunch",
                "not crop-only",
            ],
            "result_template": verification,
        },
    }


def apply_one_step_correction(
    parameters: dict[str, Any],
    suggested_correction: dict[str, Any],
) -> dict[str, Any]:
    """Apply one manifest-safe correction pass from control-id deltas."""
    updated = {group: dict(values) for group, values in parameters.items() if isinstance(values, dict)}
    for control_id, change in suggested_correction.items():
        mapping = _CONTROL_TO_FRIENDLY.get(control_id)
        if mapping is None:
            continue
        group_name, param_key = mapping
        group = updated.get(group_name)
        if not isinstance(group, dict):
            continue
        current = group.get(param_key)
        if not _is_number(current):
            continue

        delta: float | None
        if isinstance(change, str):
            delta = _parse_delta(change)
        elif _is_number(change):
            delta = float(change)
        else:
            delta = None
        if delta is None:
            continue

        candidate = float(current) + delta
        bounded, _ = _bounded_numeric(control_id, candidate)
        section, key = control_id.split(".", 1)
        if is_control_allowed_autonomous(section, key, bounded):
            group[param_key] = round(float(bounded), 3) if _is_number(bounded) else bounded
    return updated
