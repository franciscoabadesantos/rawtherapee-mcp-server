"""Predictive manifest-backed planning helpers for autonomous RAW editing."""

from __future__ import annotations

from typing import Any, TypeGuard

from rawtherapee_mcp.control_policy import (
    get_approved_curve,
    is_control_allowed_autonomous,
    load_manifest,
)

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
EXPORT_SCORE_MINIMUMS = {
    "subject_hierarchy_score": 7.0,
    "thumbnail_subject_read_score": 7.0,
    "artifact_free_score": 8.0,
    "naturalness_score": 7.0,
}
MEANINGFUL_NON_CROP_MINIMUM = 7.0
NON_CROP_PASS_FIELDS = (
    "subject_separation_improvement",
    "non_crop_tonal_improvement",
    "color_intent_improvement",
    "highlight_shadow_quality",
)

_CONTROL_TO_FRIENDLY: dict[str, tuple[str, str]] = {
    "Exposure.Compensation": ("exposure", "compensation"),
    "Exposure.Contrast": ("exposure", "contrast"),
    "Exposure.Saturation": ("exposure", "saturation"),
    "Exposure.Black": ("exposure", "black"),
    "Exposure.HighlightCompr": ("exposure", "highlight_compression"),
    "Exposure.HighlightComprThreshold": ("highlight_rolloff", "highlight_compression_threshold"),
    "Exposure.CurveMode": ("tone_curve", "curve_mode"),
    "Exposure.Curve": ("tone_curve", "curve"),
    "Exposure.Curve2": ("tone_curve", "curve2"),
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


def _clamp_score(value: float, *, lower: float = 0.0, upper: float = 10.0) -> float:
    return round(max(lower, min(upper, value)), 1)


def _perceived_non_crop_improvement(
    *,
    pass_count: int,
    strongest_score: float,
    crop_contribution: float,
) -> str:
    if pass_count >= 3 or strongest_score >= 8.5:
        return "strong"
    if pass_count >= 2:
        return "moderate"
    if strongest_score >= 5.5 and crop_contribution < 7.0:
        return "weak"
    return "none"


def _non_crop_quality_reason(
    *,
    quality_passed: bool,
    pass_fields: list[str],
    perceived_non_crop_improvement: str,
    crop_contribution: float,
) -> str:
    labels = {
        "subject_separation_improvement": "subject separation",
        "non_crop_tonal_improvement": "midtone depth",
        "color_intent_improvement": "color presence",
        "highlight_shadow_quality": "highlight/shadow control",
    }
    if quality_passed:
        visible = [labels[field] for field in pass_fields[:3]]
        if len(visible) > 1:
            joined = ", ".join(visible[:-1]) + f", and {visible[-1]}"
        else:
            joined = visible[0]
        return f"{joined} improve visibly before any crop is applied."
    if crop_contribution >= 7.0 and perceived_non_crop_improvement in {"none", "weak"}:
        return "Framing changes carry most of the gain while the base tonal/color edit remains weak before crop."
    return (
        "Tonal/color changes are numerically visible but do not materially improve subject separation "
        "or visual intent."
    )


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


def _suggested_value(
    control_id: str,
    severity: float,
    direction: float,
    intensity_scale: float,
    strength: float = 0.45,
) -> object:
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
            proposed = float(default_value) + (span * strength * amplitude)
        else:
            proposed = float(default_value) - (span * strength * amplitude)
    else:
        proposed = float(default_value) + (10.0 * direction * severity * intensity_scale)

    bounded, _ = _bounded_numeric(control_id, proposed)
    if value_type == "integer" and _is_number(bounded):
        return int(round(float(bounded)))
    return round(float(bounded), 3) if _is_number(bounded) else bounded


def _hierarchy_boost_controls(
    diagnosis: list[dict[str, Any]],
    intensity: str,
) -> tuple[list[tuple[str, object]], bool]:
    hierarchy_issues = {
        "flat_midtone_geometry",
        "weak_subject_readability",
        "low_thumbnail_impact",
    }
    severities = [
        float(item.get("severity", 0.5))
        for item in diagnosis
        if str(item.get("issue", "")) in hierarchy_issues
    ]
    if len(severities) < 2:
        return [], False

    scale = _INTENSITY_SCALE[_normalize_intensity(intensity)]
    boost_severity = max(severities)
    readability_severity = max(
        [
            float(item.get("severity", 0.5))
            for item in diagnosis
            if str(item.get("issue", "")) == "weak_subject_readability"
        ],
        default=boost_severity,
    )
    return [
        ("Exposure.Contrast", _suggested_value("Exposure.Contrast", boost_severity, 1.0, scale, strength=0.60)),
        ("Luminance Curve.Enabled", True),
        (
            "Luminance Curve.Contrast",
            _suggested_value("Luminance Curve.Contrast", boost_severity, 1.0, scale, strength=0.75),
        ),
        ("Luminance Curve.AvoidColorShift", True),
        ("SharpenMicro.Enabled", True),
        ("SharpenMicro.Amount", _suggested_value("SharpenMicro.Amount", boost_severity, 1.0, scale, strength=0.60)),
        (
            "Exposure.Compensation",
            _suggested_value("Exposure.Compensation", readability_severity, 1.0, scale, strength=0.50),
        ),
    ], True


def _curve_avoid_contexts(
    *,
    style: str,
    user_brief: str | None,
    issue_names: set[str],
) -> set[str]:
    text = f"{style} {user_brief or ''}".lower()
    avoid: set[str] = set()
    if any(token in text for token in ("portrait", "skin", "face")):
        avoid.add("portrait_skin_fragile")
    if any(token in text for token in ("night", "iso", "high iso", "low light")):
        avoid.add("night_high_iso")
    if {"bright_sky_needs_control", "washed_highlights"} & issue_names:
        avoid.add("already_high_contrast")
    return avoid


def _approved_curve_controls(
    *,
    diagnosis: list[dict[str, Any]],
    style: str,
    user_brief: str | None,
) -> tuple[list[tuple[str, object]], list[dict[str, Any]]]:
    issue_names = _issue_names(diagnosis)
    hierarchy_hits = issue_names & {"flat_midtone_geometry", "weak_subject_readability", "low_thumbnail_impact"}
    if len(hierarchy_hits) < 2:
        return [], []

    curve = get_approved_curve("tone_curve.midtone_pop_v1")
    if not curve or curve.get("autonomous_allowed") is not True:
        return [], []

    allowed_contexts = {str(item) for item in curve.get("allowed_contexts", []) if isinstance(item, str)}
    if not hierarchy_hits & allowed_contexts:
        return [], []

    avoid_contexts = {str(item) for item in curve.get("avoid_contexts", []) if isinstance(item, str)}
    active_avoid_contexts = _curve_avoid_contexts(style=style, user_brief=user_brief, issue_names=issue_names)
    if active_avoid_contexts & avoid_contexts:
        return [], []

    curve_mode = str(curve.get("curve_mode", "Standard"))
    curve_string = str(curve.get("curve_string", ""))
    curve2 = str(curve.get("curve2", "0;"))
    if not curve_string:
        return [], []

    reason = " + ".join(sorted(hierarchy_hits))
    return [
        ("Exposure.CurveMode", curve_mode),
        ("Exposure.Curve", curve_string),
        ("Exposure.Curve2", curve2),
    ], [
        {
            "id": str(curve.get("id", "tone_curve.midtone_pop_v1")),
            "reason": reason,
            "risk": "may increase harshness; checked by export gate",
            "intended_effect": str(curve.get("intended_effect", "")),
        }
    ]


def _planned_controls_from_diagnosis(
    diagnosis: list[dict[str, Any]],
    intensity: str,
) -> tuple[list[tuple[str, object]], list[str], bool]:
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
                    ("Vibrance.Pastels", _suggested_value("Vibrance.Pastels", severity, 1.0, scale, strength=0.85)),
                    ("Vibrance.Saturated", _suggested_value("Vibrance.Saturated", severity, 1.0, scale, strength=0.50)),
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

    boost_controls, hierarchy_boost_applied = _hierarchy_boost_controls(diagnosis, intensity)
    controls.extend(boost_controls)
    return controls, blocked_considered, hierarchy_boost_applied


def _merge_control_values(pairs: list[tuple[str, object]]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for control_id, value in pairs:
        if control_id not in merged:
            merged[control_id] = value
            continue
        existing = merged[control_id]
        if _is_number(existing) and _is_number(value):
            entry = _manifest_entry(control_id)
            default = _default_value_from_manifest(entry) if entry is not None else 0
            if _is_number(default):
                existing_delta = float(existing) - float(default)
                value_delta = float(value) - float(default)
                if existing_delta * value_delta >= 0:
                    merged[control_id] = existing if abs(existing_delta) >= abs(value_delta) else value
                else:
                    merged[control_id] = (float(existing) + float(value)) / 2.0
            else:
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


def score_predictive_export_decision(
    *,
    validation_allowed: bool,
    global_visible_difference_score: float,
    subject_hierarchy_score: float,
    thumbnail_subject_read_score: float,
    color_quality_score: float,
    naturalness_score: float,
    artifact_free_score: float,
    crop_dependency: str,
    global_pixel_difference: float | None = None,
    non_crop_tonal_improvement: float = 0.0,
    subject_separation_improvement: float = 0.0,
    color_intent_improvement: float = 0.0,
    highlight_shadow_quality: float = 0.0,
    composition_improvement: float = 0.0,
    crop_contribution: float = 0.0,
    perceived_non_crop_improvement: str | None = None,
) -> dict[str, Any]:
    """Return strict export/proof decision from separated verification scores."""
    normalized_global_difference = float(global_pixel_difference or global_visible_difference_score)
    non_crop_scores = {
        "subject_separation_improvement": float(subject_separation_improvement),
        "non_crop_tonal_improvement": float(non_crop_tonal_improvement),
        "color_intent_improvement": float(color_intent_improvement),
        "highlight_shadow_quality": float(highlight_shadow_quality),
    }
    non_crop_pass_fields = [
        field for field, value in non_crop_scores.items() if value >= MEANINGFUL_NON_CROP_MINIMUM
    ]
    non_crop_quality_passed = len(non_crop_pass_fields) >= 2
    strongest_non_crop_score = max(non_crop_scores.values(), default=0.0)
    normalized_crop_contribution = float(crop_contribution)
    normalized_perceived = perceived_non_crop_improvement or _perceived_non_crop_improvement(
        pass_count=len(non_crop_pass_fields),
        strongest_score=strongest_non_crop_score,
        crop_contribution=normalized_crop_contribution,
    )
    crop_only_improvement = (
        normalized_crop_contribution >= 7.0
        and float(composition_improvement) >= 7.0
        and not non_crop_quality_passed
    )
    export_gate_passed = (
        validation_allowed
        and non_crop_quality_passed
        and subject_hierarchy_score >= EXPORT_SCORE_MINIMUMS["subject_hierarchy_score"]
        and thumbnail_subject_read_score >= EXPORT_SCORE_MINIMUMS["thumbnail_subject_read_score"]
        and artifact_free_score >= EXPORT_SCORE_MINIMUMS["artifact_free_score"]
        and naturalness_score >= EXPORT_SCORE_MINIMUMS["naturalness_score"]
        and crop_dependency != "primary"
        and normalized_crop_contribution < 7.0
    )
    if export_gate_passed:
        decision = "export"
    elif crop_only_improvement or crop_dependency == "primary":
        decision = "crop_only_improvement"
    elif not non_crop_quality_passed:
        decision = "failed_edit_quality" if normalized_global_difference >= 5.5 else "proof_only"
    elif normalized_perceived in {"none", "weak"}:
        decision = "proof_only"
    else:
        decision = "proof_plus"

    return {
        "decision": decision,
        "export_gate_passed": export_gate_passed,
        "global_pixel_difference": normalized_global_difference,
        "non_crop_tonal_improvement": float(non_crop_tonal_improvement),
        "subject_separation_improvement": float(subject_separation_improvement),
        "color_intent_improvement": float(color_intent_improvement),
        "highlight_shadow_quality": float(highlight_shadow_quality),
        "composition_improvement": float(composition_improvement),
        "crop_contribution": normalized_crop_contribution,
        "perceived_non_crop_improvement": normalized_perceived,
        "meaningful_non_crop_edit": non_crop_quality_passed,
        "non_crop_quality_pass_count": len(non_crop_pass_fields),
        "non_crop_quality_pass_fields": non_crop_pass_fields,
        "crop_only_improvement": crop_only_improvement,
        "non_crop_edit_quality": "pass" if non_crop_quality_passed else "fail",
        "non_crop_edit_quality_reason": _non_crop_quality_reason(
            quality_passed=non_crop_quality_passed,
            pass_fields=non_crop_pass_fields,
            perceived_non_crop_improvement=normalized_perceived,
            crop_contribution=normalized_crop_contribution,
        ),
        "gate_requirements": {
            "meaningful_non_crop_requirements": {
                "minimum_score": MEANINGFUL_NON_CROP_MINIMUM,
                "minimum_pass_count": 2,
                "fields": list(NON_CROP_PASS_FIELDS),
            },
            "subject_hierarchy_score_min": EXPORT_SCORE_MINIMUMS["subject_hierarchy_score"],
            "thumbnail_subject_read_score_min": EXPORT_SCORE_MINIMUMS["thumbnail_subject_read_score"],
            "artifact_free_score_min": EXPORT_SCORE_MINIMUMS["artifact_free_score"],
            "naturalness_score_min": EXPORT_SCORE_MINIMUMS["naturalness_score"],
            "crop_dependency": "not primary",
            "crop_contribution_max_for_export": 6.9,
            "validation_allowed": True,
        },
        "scoring_guidance": (
            "Hierarchy score should answer: does the intended subject become easier and faster "
            "to read than competing structures?"
        ),
    }


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

    issue_controls, blocked_considered, hierarchy_boost_applied = _planned_controls_from_diagnosis(
        diagnosis_items, intensity
    )
    merged_controls = _merge_control_values(issue_controls)
    approved_curve_controls, approved_curves_used = _approved_curve_controls(
        diagnosis=diagnosis_items,
        style=style,
        user_brief=user_brief,
    )
    merged_controls = _merge_control_values(approved_curve_controls + list(merged_controls.items()))

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
                "primary subject should separate faster from poles/wires/background",
                "midtone rail/street geometry should gain clearer depth",
            ]
        )
    if "dull_color_presence" in issue_names:
        expected_effect.append("color presence should increase without fake HDR or phone-filter saturation")
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
    global_visible_difference_score = _clamp_score(5.5 + (severity_sum * 1.2) + (len(non_crop_groups) * 0.3))
    subject_separation_improvement = _clamp_score(
        4.2
        + (1.1 if "flat_midtone_geometry" in issue_names else 0.0)
        + (1.0 if "weak_subject_readability" in issue_names else 0.0)
        + (0.5 if "low_thumbnail_impact" in issue_names else 0.0)
        + (0.2 if "dull_color_presence" in issue_names else 0.0)
    )
    non_crop_tonal_improvement = _clamp_score(
        4.1
        + (1.1 if "flat_midtone_geometry" in issue_names else 0.0)
        + (0.9 if "blocked_shadows" in issue_names else 0.0)
        + (0.7 if "bright_sky_needs_control" in issue_names else 0.0)
        + (0.5 if "washed_highlights" in issue_names else 0.0)
    )
    color_intent_improvement = _clamp_score(
        4.2
        + (1.5 if "dull_color_presence" in issue_names else 0.0)
        + (0.9 if "too_cool_or_clinical" in issue_names else 0.0)
        + (0.7 if "too_warm_or_orange" in issue_names else 0.0)
        + (0.5 if "green_yellow_cast" in issue_names else 0.0)
    )
    highlight_shadow_quality = _clamp_score(
        4.0
        + (1.4 if "bright_sky_needs_control" in issue_names else 0.0)
        + (1.2 if "washed_highlights" in issue_names else 0.0)
        + (1.0 if "blocked_shadows" in issue_names else 0.0)
    )
    composition_improvement = _clamp_score(
        4.0
        + (2.3 if "crop_distraction_edges" in issue_names else 0.0)
        + (1.7 if "needs_mild_straightening_or_geometry" in issue_names else 0.0)
    )
    crop_contribution = _clamp_score(
        2.0
        + (4.0 if crop_dependency == "primary" else 0.0)
        + (2.8 if "crop_distraction_edges" in issue_names else 0.0)
        + (1.2 if "needs_mild_straightening_or_geometry" in issue_names else 0.0)
    )
    subject_hierarchy_score = _clamp_score(subject_separation_improvement)
    thumbnail_subject_read_score = _clamp_score(
        4.4
        + (0.8 if "low_thumbnail_impact" in issue_names else 0.0)
        + (0.7 if "weak_subject_readability" in issue_names else 0.0)
        + (0.5 if "flat_midtone_geometry" in issue_names else 0.0)
        + (0.2 if "dull_color_presence" in issue_names else 0.0)
    )
    color_quality_score = _clamp_score(color_intent_improvement + 0.4)
    naturalness_score = 8.0
    artifact_free_score = 9.0

    if "proof_only_needed" in issue_names:
        global_visible_difference_score = min(global_visible_difference_score, 5.4)
        subject_hierarchy_score = min(subject_hierarchy_score, 5.5)
        thumbnail_subject_read_score = min(thumbnail_subject_read_score, 5.5)
        subject_separation_improvement = min(subject_separation_improvement, 5.5)
        non_crop_tonal_improvement = min(non_crop_tonal_improvement, 5.5)
        color_intent_improvement = min(color_intent_improvement, 5.5)
        highlight_shadow_quality = min(highlight_shadow_quality, 5.5)

    quality_seed = score_predictive_export_decision(
        validation_allowed=True,
        global_visible_difference_score=global_visible_difference_score,
        subject_hierarchy_score=subject_hierarchy_score,
        thumbnail_subject_read_score=thumbnail_subject_read_score,
        color_quality_score=color_quality_score,
        naturalness_score=naturalness_score,
        artifact_free_score=artifact_free_score,
        crop_dependency=crop_dependency,
        global_pixel_difference=global_visible_difference_score,
        non_crop_tonal_improvement=non_crop_tonal_improvement,
        subject_separation_improvement=subject_separation_improvement,
        color_intent_improvement=color_intent_improvement,
        highlight_shadow_quality=highlight_shadow_quality,
        composition_improvement=composition_improvement,
        crop_contribution=crop_contribution,
    )
    gate_decision = quality_seed
    hierarchy_improvement_score = subject_hierarchy_score
    visible_difference_score = global_visible_difference_score

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
        "recommendation": "accept" if gate_decision["decision"] == "export" else gate_decision["decision"],
        "suggested_correction": (
            {"Vibrance.Pastels": "+3", "Exposure.HighlightCompr": "-3"}
            if gate_decision["decision"] == "proof_plus"
            else {}
        ),
    }

    return {
        "diagnosis": diagnosis,
        "parameters": parameters,
        "expected_effect": expected_effect,
        "blocked_controls_considered": blocked_controls_considered,
        "approved_curves_used": approved_curves_used,
        "clamped": clamped,
        "scores": {
            "global_visible_difference_score": global_visible_difference_score,
            "global_pixel_difference": global_visible_difference_score,
            "subject_hierarchy_score": subject_hierarchy_score,
            "thumbnail_subject_read_score": thumbnail_subject_read_score,
            "color_quality_score": color_quality_score,
            "naturalness_score": naturalness_score,
            "artifact_free_score": artifact_free_score,
            "crop_dependency": crop_dependency,
            "non_crop_tonal_improvement": non_crop_tonal_improvement,
            "subject_separation_improvement": subject_separation_improvement,
            "color_intent_improvement": color_intent_improvement,
            "highlight_shadow_quality": highlight_shadow_quality,
            "composition_improvement": composition_improvement,
            "crop_contribution": crop_contribution,
            "perceived_non_crop_improvement": gate_decision["perceived_non_crop_improvement"],
            "meaningful_non_crop_edit": gate_decision["meaningful_non_crop_edit"],
            "non_crop_edit_quality": gate_decision["non_crop_edit_quality"],
            "non_crop_edit_quality_reason": gate_decision["non_crop_edit_quality_reason"],
            "approved_curves_used": approved_curves_used,
            "hierarchy_boost_applied": hierarchy_boost_applied,
            "artifact_check": "pass" if artifact_free_score >= 8.0 else "fail",
            "decision": gate_decision["decision"],
            "export_gate_passed": gate_decision["export_gate_passed"],
            "gate_requirements": gate_decision["gate_requirements"],
            "scoring_guidance": gate_decision["scoring_guidance"],
            # Backward-compatible aliases for older callers/reports.
            "visible_difference_score": visible_difference_score,
            "hierarchy_improvement_score": hierarchy_improvement_score,
        },
        "verification_contract": {
            "check": [
                "subject readability improved",
                "thumbnail impact improved",
                "sky remains believable",
                "no local-contrast crunch",
                "not crop-only",
            ],
            "scoring_guidance": gate_decision["scoring_guidance"],
            "hierarchy_boost_applied": hierarchy_boost_applied,
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
