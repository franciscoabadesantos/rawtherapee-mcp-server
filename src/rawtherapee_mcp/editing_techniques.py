"""Safe, reusable editing techniques for autonomous visual workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict

ParameterSet = dict[str, dict[str, Any]]

_LINEAR_CURVE = "0;"
_GENTLE_S_CURVE = "3;0;0;0.24;0.20;0.50;0.56;0.78;0.86;1;1;"
_TONAL_SEPARATION_CURVE = "3;0;0;0.30;0.28;0.58;0.64;0.86;0.90;1;1;"
_MIST_LUMA_CURVE = "3;0;0.08;0.36;0.34;0.70;0.66;1;0.96;"
_SILHOUETTE_CURVE = "3;0;0;0.34;0.30;0.66;0.62;1;0.90;"
_BLUE_S_CURVE = "1;0.00;0.50;0.35;0.35;0.57;0.56;0.35;0.35;0.72;0.47;0.35;0.35;1.00;0.50;0.35;0.35;"
_GREEN_SOFT_CURVE = "1;0.00;0.50;0.35;0.35;0.33;0.43;0.35;0.35;0.47;0.44;0.35;0.35;1.00;0.50;0.35;0.35;"


class TechniqueDefinition(TypedDict):
    """Description of one reusable safe editing technique."""

    name: str
    purpose: str
    parameters: ParameterSet
    risk_note: str
    risk_tags: list[str]
    when_to_use: list[str]
    when_to_avoid: list[str]


class CombinedTechniques(TypedDict):
    """Merged technique parameters and merge diagnostics."""

    parameters: ParameterSet
    techniques_used: list[str]
    unknown_techniques: list[str]
    overwritten_parameters: list[str]


def _make_technique(
    *,
    name: str,
    purpose: str,
    parameters: ParameterSet,
    risk_note: str,
    risk_tags: list[str] | None = None,
    when_to_use: list[str] | None = None,
    when_to_avoid: list[str] | None = None,
) -> TechniqueDefinition:
    return {
        "name": name,
        "purpose": purpose,
        "parameters": parameters,
        "risk_note": risk_note,
        "risk_tags": risk_tags or [],
        "when_to_use": when_to_use or [],
        "when_to_avoid": when_to_avoid or [],
    }


TECHNIQUE_REGISTRY: dict[str, TechniqueDefinition] = {
    "gentle_s_curve": _make_technique(
        name="gentle_s_curve",
        purpose="Add balanced tonal shape without aggressive contrast.",
        parameters={
            "tone_curve": {
                "curve_mode": "Standard",
                "curve_mode2": "Standard",
                "curve": _GENTLE_S_CURVE,
                "curve2": _LINEAR_CURVE,
            }
        },
        risk_note="Can look too polished if combined with heavy local contrast.",
    ),
    "gentle_tonal_separation": _make_technique(
        name="gentle_tonal_separation",
        purpose="Separate lights/mids/shadows for clarity while staying natural.",
        parameters={
            "tone_curve": {
                "curve_mode": "Standard",
                "curve_mode2": "Standard",
                "curve": _TONAL_SEPARATION_CURVE,
                "curve2": _LINEAR_CURVE,
            },
            "luminance_curve": {
                "enabled": True,
                "contrast": 6,
                "avoid_color_shift": True,
            },
        },
        risk_note="Can flatten mood if stacked with strong shadow lifting.",
    ),
    "clean_midtone_contrast": _make_technique(
        name="clean_midtone_contrast",
        purpose="Increase subject readability via controlled midtone separation.",
        parameters={
            "luminance_curve": {
                "enabled": True,
                "contrast": 8,
                "avoid_color_shift": True,
                "lh_curve": "3;0;0;0.36;0.42;0.70;0.62;1;1;",
                "hh_curve": "3;0;0;0.56;0.64;0.86;0.82;1;0.94;",
            }
        },
        risk_note="Can look gritty if combined with excessive sharpening.",
        risk_tags=["color_presence", "generic_pop"],
    ),
    "soft_highlight_rolloff": _make_technique(
        name="soft_highlight_rolloff",
        purpose="Protect bright areas and keep transitions smooth.",
        parameters={
            "highlight_rolloff": {
                "enabled": True,
                "method": "Coloropp",
                "highlight_compression": 28,
                "highlight_compression_threshold": 34,
                "highlights": -14,
                "highlight_tonal_width": 72,
                "radius": 36,
            }
        },
        risk_note="Too much rolloff can make the image look muted.",
    ),
    "subtle_shadow_depth": _make_technique(
        name="subtle_shadow_depth",
        purpose="Recover depth in darker regions without crushing detail.",
        parameters={"exposure": {"black": -3, "contrast": 3}},
        risk_note="Can hide detail if used on already low-key images.",
    ),
    "subject_readability_without_hdr": _make_technique(
        name="subject_readability_without_hdr",
        purpose="Lift readability with restrained global adjustments.",
        parameters={
            "exposure": {"compensation": 0.20, "contrast": 7, "highlight_compression": 12},
            "luminance_curve": {"enabled": True, "contrast": 5, "avoid_color_shift": True},
        },
        risk_note="Can feel generic if applied without clear anchor intent.",
    ),
    "preserve_silhouette_tone": _make_technique(
        name="preserve_silhouette_tone",
        purpose="Keep silhouette identity while avoiding clipped highlights.",
        parameters={
            "exposure": {"compensation": -0.05, "black": -4, "contrast": 2, "highlight_compression": 18},
            "tone_curve": {"curve_mode": "Standard", "curve": _SILHOUETTE_CURVE},
        },
        risk_note="Wrong for images that require full facial lift.",
    ),
    "muted_fog_contrast": _make_technique(
        name="muted_fog_contrast",
        purpose="Protect mist/fog softness and avoid over-clarity.",
        parameters={
            "exposure": {"contrast": -6, "saturation": -3},
            "luminance_curve": {"enabled": True, "contrast": -5, "l_curve": _MIST_LUMA_CURVE},
        },
        risk_note="Can look flat in already low-contrast scenes.",
    ),
    "shape_light_break_tonality": _make_technique(
        name="shape_light_break_tonality",
        purpose="Emphasize directional light transitions without fake HDR.",
        parameters={
            "exposure": {"contrast": 5, "highlight_compression": 16},
            "luminance_curve": {
                "enabled": True,
                "contrast": 7,
                "avoid_color_shift": True,
                "lh_curve": "3;0;0;0.30;0.34;0.62;0.56;1;0.98;",
            },
        },
        risk_note="Can look dramatic if stacked with aggressive curves.",
    ),
    "subtle_water_luma_depth": _make_technique(
        name="subtle_water_luma_depth",
        purpose="Create perceived depth in water through luminance structure.",
        parameters={
            "luminance_curve": {
                "enabled": True,
                "contrast": 7,
                "avoid_color_shift": True,
                "lh_curve": "3;0;0;0.38;0.44;0.72;0.62;1;1;",
                "hh_curve": "3;0;0;0.58;0.66;0.88;0.82;1;0.92;",
            },
            "exposure": {"saturation": 1},
        },
        risk_note="Can over-separate if scene is naturally hazy.",
    ),
    "controlled_blue_presence": _make_technique(
        name="controlled_blue_presence",
        purpose="Strengthen blue presence while avoiding synthetic cyan.",
        parameters={"hsv_equalizer": {"enabled": True, "s_curve": _BLUE_S_CURVE, "v_curve": _BLUE_S_CURVE}},
        risk_note="Can look unreal on non-blue-dominant scenes.",
        risk_tags=["cyan_shift", "blue_split", "synthetic_blue"],
    ),
    "natural_green_compression": _make_technique(
        name="natural_green_compression",
        purpose="Compress neon greens into believable foliage tones.",
        parameters={"hsv_equalizer": {"enabled": True, "s_curve": _GREEN_SOFT_CURVE}},
        risk_note="Can mute fresh foliage if overused.",
        risk_tags=["green_shift"],
    ),
    "reduce_green_gray_cast_safe": _make_technique(
        name="reduce_green_gray_cast_safe",
        purpose="Neutralize mild green-gray drift safely.",
        parameters={
            "white_balance": {"green": 0.99},
            "luminance_curve": {"enabled": True, "chromaticity": 3, "avoid_color_shift": True},
        },
        risk_note="May neutralize intentional cool mood if used blindly.",
    ),
    "skin_safe_warmth": _make_technique(
        name="skin_safe_warmth",
        purpose="Add warm feeling while protecting skin from orange shifts.",
        parameters={
            "vibrance": {
                "enabled": True,
                "pastels": 8,
                "saturated": 3,
                "protectskins": True,
                "avoidcolorshift": True,
                "pastsattog": True,
                "psthreshold": [10, 72],
            }
        },
        risk_note="Can still drift warm on heavily tungsten scenes.",
        risk_tags=["warm_shift", "orange_shift"],
    ),
    "clean_neutral_balance": _make_technique(
        name="clean_neutral_balance",
        purpose="Keep neutrals stable and color relationships believable.",
        parameters={
            "white_balance": {"method": "Camera", "green": 1.0},
            "luminance_curve": {"enabled": True, "avoid_color_shift": True, "red_skin_protection": 12},
        },
        risk_note="Not ideal when a strong color cast is intentional.",
    ),
    "preserve_material_texture": _make_technique(
        name="preserve_material_texture",
        purpose="Retain material realism without crunch artifacts.",
        parameters={
            "sharpening": {"enabled": True, "radius": 0.45, "amount": 105, "threshold": [20, 80, 1800, 1200]},
            "noise_reduction": {"enabled": True, "luminance": 8, "chrominance": 9},
        },
        risk_note="Texture can turn brittle if combined with strong local contrast.",
    ),
    "calm_global_saturation": _make_technique(
        name="calm_global_saturation",
        purpose="Reduce filter-like color intensity while keeping life in the frame.",
        parameters={"exposure": {"saturation": -4}, "vibrance": {"enabled": True, "pastels": 2, "saturated": -4}},
        risk_note="May feel too subdued for celebratory scenes.",
    ),
    "gentle_structure_without_crunch": _make_technique(
        name="gentle_structure_without_crunch",
        purpose="Improve micro detail perception using conservative structure settings.",
        parameters={
            "microcontrast": {"enabled": True, "strength": 8},
        },
        risk_note="Keeps autonomous structure work off RawTherapee Local Contrast due to artifact risk.",
        risk_tags=["local_contrast_artifact"],
    ),
}


def list_editing_techniques() -> list[TechniqueDefinition]:
    """Return sorted technique metadata for planning and explainability."""
    return [deepcopy(TECHNIQUE_REGISTRY[name]) for name in sorted(TECHNIQUE_REGISTRY)]


def technique_to_parameters(technique_name: str) -> ParameterSet:
    """Return a deep copy of parameters for one technique."""
    technique = TECHNIQUE_REGISTRY.get(technique_name)
    if technique is None:
        msg = f"Unknown editing technique: {technique_name}"
        raise KeyError(msg)
    return deepcopy(technique["parameters"])


def technique_risk_tags(technique_name: str) -> list[str]:
    """Return risk tags for one technique."""
    technique = TECHNIQUE_REGISTRY.get(technique_name)
    if technique is None:
        msg = f"Unknown editing technique: {technique_name}"
        raise KeyError(msg)
    return deepcopy(technique["risk_tags"])


def combine_techniques(technique_names: list[str]) -> CombinedTechniques:
    """Merge technique parameter dictionaries with deterministic override order."""
    merged: ParameterSet = {}
    overwritten_parameters: list[str] = []
    techniques_used: list[str] = []
    unknown_techniques: list[str] = []

    for name in technique_names:
        technique = TECHNIQUE_REGISTRY.get(name)
        if technique is None:
            unknown_techniques.append(name)
            continue

        techniques_used.append(name)
        for group_name, values in technique["parameters"].items():
            target_group = merged.setdefault(group_name, {})
            for key, value in values.items():
                if key in target_group:
                    overwritten_parameters.append(f"{group_name}.{key}")
                target_group[key] = deepcopy(value)

    return {
        "parameters": merged,
        "techniques_used": techniques_used,
        "unknown_techniques": unknown_techniques,
        "overwritten_parameters": sorted(set(overwritten_parameters)),
    }
