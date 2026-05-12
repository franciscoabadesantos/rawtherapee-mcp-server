"""Advanced tone and color parameter helpers for editorial profile generation."""

from __future__ import annotations

from typing import Any

ParameterSet = dict[str, dict[str, Any]]

# RT curve strings used as reliable defaults for tone/color shaping.
_LINEAR_CURVE = "0;"
_GENTLE_S_CURVE = "3;0;0;0.22;0.18;0.50;0.56;0.78;0.86;1;1;"
_CINEMATIC_SOFT_CURVE = "3;0;0.06;0.26;0.24;0.52;0.55;0.80;0.84;1;0.96;"
_LIFTED_BLACKS_CURVE = "3;0;0.07;0.30;0.29;0.62;0.69;1;1;"
_HSV_SOFT_GREEN_CURVE = "1;0.00;0.50;0.35;0.35;0.33;0.45;0.35;0.35;0.66;0.52;0.35;0.35;1.00;0.50;0.35;0.35;"
_HSV_SKY_SAT_CURVE = "1;0.00;0.50;0.35;0.35;0.55;0.58;0.35;0.35;0.70;0.48;0.35;0.35;1.00;0.50;0.35;0.35;"
_HSV_BLUE_VALUE_CURVE = "1;0.00;0.50;0.35;0.35;0.62;0.60;0.35;0.35;0.78;0.52;0.35;0.35;1.00;0.50;0.35;0.35;"
_HSV_ORANGE_SAT_CURVE = "1;0.00;0.50;0.35;0.35;0.08;0.46;0.35;0.35;0.18;0.44;0.35;0.35;1.00;0.50;0.35;0.35;"
_HSV_ORANGE_VALUE_CURVE = "1;0.00;0.50;0.35;0.35;0.08;0.55;0.35;0.35;0.18;0.57;0.35;0.35;1.00;0.50;0.35;0.35;"


def merge_parameter_sets(*parameter_sets: ParameterSet) -> ParameterSet:
    """Deep-merge grouped PP3 parameter dictionaries."""
    merged: ParameterSet = {}
    for param_set in parameter_sets:
        for group_name, values in param_set.items():
            if group_name not in merged:
                merged[group_name] = {}
            merged[group_name].update(values)
    return merged


def gentle_s_curve() -> ParameterSet:
    """Global tonal S-curve with mild highlight protection."""
    return {
        "tone_curve": {
            "curve_mode": "Standard",
            "curve_mode2": "Standard",
            "curve": _GENTLE_S_CURVE,
            "curve2": _LINEAR_CURVE,
        }
    }


def clean_midtone_contrast() -> ParameterSet:
    """Add midtone contrast while protecting shadows and highlights."""
    return {
        "luminance_curve": {
            "enabled": True,
            "contrast": 8,
            "lh_curve": "3;0;0;0.35;0.42;0.70;0.62;1;1;",
            "hh_curve": "3;0;0;0.55;0.63;0.85;0.82;1;0.94;",
        }
    }


def soft_highlight_rolloff() -> ParameterSet:
    """Roll off highlights without flattening midtones."""
    return {
        "highlight_rolloff": {
            "enabled": True,
            "method": "Coloropp",
            "highlight_compression": 30,
            "highlight_compression_threshold": 33,
            "highlights": -18,
            "highlight_tonal_width": 70,
            "radius": 38,
        }
    }


def lifted_film_blacks() -> ParameterSet:
    """Lift the tonal toe for a filmic black floor."""
    return {
        "tone_curve": {
            "curve_mode": "Standard",
            "curve": _LIFTED_BLACKS_CURVE,
        },
        "exposure": {
            "black": -4,
        },
    }


def warm_highlights_cool_shadows() -> ParameterSet:
    """Color separation with warm highlights and cooler shadows."""
    return {
        "color_balance": {
            "enabled": True,
            "method": "Lab",
            "luma_mode": True,
            "red_low": -8,
            "green_low": 0,
            "blue_low": 12,
            "sat_low": 8,
            "red_high": 10,
            "green_high": 2,
            "blue_high": -6,
            "sat_high": 7,
            "balance": 6,
            "strength": 28,
            "autosat": True,
        }
    }


def protect_skin_reduce_orange() -> ParameterSet:
    """Reduce orange drift and protect skin saturation."""
    return {
        "vibrance": {
            "enabled": True,
            "pastels": 6,
            "saturated": 4,
            "protectskins": True,
            "avoidcolorshift": True,
            "pastsattog": True,
            "psthreshold": [10, 72],
        },
        "hsv_equalizer": {
            "enabled": True,
            "s_curve": _HSV_ORANGE_SAT_CURVE,
            "v_curve": _HSV_ORANGE_VALUE_CURVE,
        },
    }


def clean_sky_blue() -> ParameterSet:
    """Keep skies clean and avoid cyan clipping."""
    return {
        "hsv_equalizer": {
            "enabled": True,
            "s_curve": _HSV_SKY_SAT_CURVE,
            "v_curve": _HSV_BLUE_VALUE_CURVE,
        }
    }


def natural_green_control() -> ParameterSet:
    """Tame neon greens while preserving natural foliage depth."""
    return {
        "hsv_equalizer": {
            "enabled": True,
            "h_curve": _HSV_SOFT_GREEN_CURVE,
            "s_curve": _HSV_SOFT_GREEN_CURVE,
        }
    }


def reduce_green_gray_cast() -> ParameterSet:
    """Counter mild green/gray cast while staying neutral."""
    return {
        "white_balance": {"green": 0.99},
        "luminance_curve": {
            "enabled": True,
            "chromaticity": 4,
            "avoid_color_shift": True,
            "red_skin_protection": 10,
        },
    }


def warm_sand_preserve_skin() -> ParameterSet:
    """Warm travel surfaces without yellowing skin tones."""
    return merge_parameter_sets(
        warm_highlights_cool_shadows(),
        {
            "color_balance": {
                "red_mid": 3,
                "green_mid": 1,
                "blue_mid": -2,
                "balance": 8,
                "strength": 34,
            },
            "vibrance": {
                "enabled": True,
                "protectskins": True,
                "pastels": 10,
                "saturated": 6,
            },
        },
    )


def cinematic_soft_color_separation() -> ParameterSet:
    """Filmic soft contrast with warm/cool split and protected highlights."""
    return merge_parameter_sets(
        {
            "tone_curve": {
                "curve_mode": "Standard",
                "curve": _CINEMATIC_SOFT_CURVE,
            },
            "exposure": {
                "contrast": -2,
                "saturation": -5,
            },
        },
        lifted_film_blacks(),
        soft_highlight_rolloff(),
        warm_highlights_cool_shadows(),
    )
