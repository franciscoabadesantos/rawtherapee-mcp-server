"""Opinionated editorial workflow helpers for autonomous RAW editing guidance."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rawtherapee_mcp.advanced_color import (
    cinematic_soft_color_separation,
    clean_midtone_contrast,
    clean_sky_blue,
    gentle_s_curve,
    merge_parameter_sets,
    natural_green_control,
    protect_skin_reduce_orange,
    reduce_green_gray_cast,
    soft_highlight_rolloff,
    warm_sand_preserve_skin,
)

SUPPORTED_EDITORIAL_STYLES = (
    "clean_editorial",
    "warm_travel",
    "cinematic_soft",
    "natural_proof",
    "postcard_natural",
    "portrait_golden_hour",
)

_DEFAULT_RECOMMENDED_WORKFLOW = [
    "create_editorial_brief",
    "generate_editorial_candidates",
    "preview_raw or preview_before_after",
    "critique_gate",
    "adjust_profile (only when critique says refine)",
    "preview again",
    "process_raw (only if critique threshold is passed)",
]

_STYLE_PRIORITIES: dict[str, list[str]] = {
    "clean_editorial": [
        "Neutral-to-slightly-warm white balance with believable skin/foliage tones.",
        "Subject clarity first: lift subject exposure before stylization.",
        "Moderate contrast and restrained saturation for realistic polish.",
    ],
    "warm_travel": [
        "Warm highlights and richer color while preserving neutral skin.",
        "Keep travel mood optimistic but avoid phone-filter intensity.",
        "Protect yellows and reds from clipping or cartoon-like shifts.",
    ],
    "cinematic_soft": [
        "Softer contrast with gently lifted shadows and controlled highlights.",
        "Reduced saturation and atmospheric tone without gray/muddy subject.",
        "Mood is secondary to readability of face/subject.",
    ],
    "natural_proof": [
        "Technical correction first: exposure, white balance, and lens cleanup.",
        "Minimal stylization; preserve scene realism for proofing.",
        "Prefer subtle, reversible adjustments and avoid heavy tone curves.",
    ],
    "postcard_natural": [
        "Clean, bright, inviting colors with believable contrast.",
        "Enhance landscape/travel readability without fake HDR look.",
        "Keep sky, foliage, and skin natural; avoid oversaturated blues/greens.",
    ],
    "portrait_golden_hour": [
        "Preserve flattering warm light while protecting skin from orange cast.",
        "Prioritize facial exposure and texture over global contrast boosts.",
        "Keep background supportive but secondary to subject separation.",
    ],
}

_STYLE_PARAMETERS: dict[str, dict[str, Any]] = {
    "clean_editorial": {
        "exposure": {
            "compensation": 0.3,
            "contrast": 12,
            "saturation": 2,
            "highlight_compression": 20,
            "black": -2,
        },
        "white_balance": {"method": "Camera", "temperature": 5600, "green": 1.0},
        "sharpening": {"enabled": True, "radius": 0.5, "amount": 140},
        "noise_reduction": {"enabled": True, "luminance": 10, "chrominance": 10},
        "vibrance": {"enabled": True, "pastels": 10, "saturated": 4, "protectskins": True, "avoidcolorshift": True},
        "microcontrast": {"enabled": True, "strength": 18, "uniformity": 55},
    },
    "warm_travel": {
        "exposure": {
            "compensation": 0.45,
            "contrast": 14,
            "saturation": 4,
            "highlight_compression": 26,
            "black": -3,
        },
        "white_balance": {"method": "Custom", "temperature": 6000, "green": 0.99},
        "sharpening": {"enabled": True, "radius": 0.55, "amount": 145},
        "noise_reduction": {"enabled": True, "luminance": 12, "chrominance": 12},
        "vibrance": {"enabled": True, "pastels": 12, "saturated": 7, "protectskins": True, "avoidcolorshift": True},
        "microcontrast": {"enabled": True, "strength": 20, "uniformity": 54},
    },
    "cinematic_soft": {
        "exposure": {
            "compensation": 0.25,
            "contrast": -4,
            "saturation": -4,
            "highlight_compression": 34,
            "black": -4,
        },
        "white_balance": {"method": "Custom", "temperature": 5400, "green": 1.02},
        "sharpening": {"enabled": True, "radius": 0.45, "amount": 110},
        "noise_reduction": {"enabled": True, "luminance": 14, "chrominance": 14},
        "vibrance": {"enabled": True, "pastels": 4, "saturated": -2, "protectskins": True, "avoidcolorshift": True},
        "microcontrast": {"enabled": True, "strength": 15, "uniformity": 58},
    },
}

_CANDIDATE_EFFECTS: dict[str, str] = {
    "clean_editorial": "Balanced natural edit with gentle S-curve, clean tonal separation, and restrained color.",
    "warm_travel": "Warmer travel mood with highlight/shadow color separation and controlled greens/blues.",
    "cinematic_soft": "Soft cinematic mood with lifted blacks, rolled highlights, and subtle warm/cool split.",
}

_CANDIDATE_RISKS: dict[str, list[str]] = {
    "clean_editorial": [
        "Subject may still look flat or underexposed in backlit scenes.",
        "Over-sharpening can create crunchy texture in skin/foliage.",
        "Color may drift cool/green if camera WB was unstable.",
    ],
    "warm_travel": [
        "Skin may turn orange if warmth and saturation stack too far.",
        "Yellows in sand/grass can clip into a fake filter look.",
        "Shadow lift can reduce perceived depth if overdone.",
    ],
    "cinematic_soft": [
        "Image can become gray or muddy if contrast is reduced too much.",
        "Subject separation may weaken if shadows are lifted globally.",
        "Mood may look fake cinematic if saturation drops too far.",
    ],
}

_CANDIDATE_FAIL_STRATEGIES: dict[str, list[str]] = {
    "clean_editorial": [
        "If subject is still dark, raise exposure compensation before adding contrast.",
        "If colors look flat, increase saturation slightly (2-4 points) not globally aggressive.",
        "If texture is harsh, reduce sharpening amount before denoising changes.",
    ],
    "warm_travel": [
        "If skin goes orange, lower temperature and saturation before any stylistic boost.",
        "If highlights clip, increase highlight compression and reduce contrast slightly.",
        "If image looks like a phone filter, pull back warmth and vibrance first.",
    ],
    "cinematic_soft": [
        "If muddy, increase subject exposure and add small contrast recovery.",
        "If too gray, restore moderate saturation and reduce shadow lift.",
        "If subject blends into background, prioritize separation over mood.",
    ],
}


def safe_slug(value: str, fallback: str = "profile") -> str:
    """Convert free text into a path-safe slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-._")
    return cleaned or fallback


def build_editorial_brief(
    file_path: str,
    *,
    intent: str | None,
    style: str,
    output_goal: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict editing brief for the LLM's editorial loop."""
    normalized_style = style if style in SUPPORTED_EDITORIAL_STYLES else "clean_editorial"
    style_priorities = _STYLE_PRIORITIES.get(normalized_style, _STYLE_PRIORITIES["clean_editorial"])

    brief: dict[str, Any] = {
        "file_path": file_path,
        "intent": intent,
        "style": normalized_style,
        "output_goal": output_goal,
        "recommended_workflow": list(_DEFAULT_RECOMMENDED_WORKFLOW),
        "required_preview_loop_steps": [
            "Generate at least 3 distinct candidates before selecting a direction.",
            "Preview each candidate and compare against original at thumbnail size.",
            "Run critique_gate after every preview and follow its verdict strictly.",
            "Refine the biggest flaw first, then re-preview before any export decision.",
        ],
        "visual_critique_checklist": [
            "Is subject/face clearly visible and separated from background?",
            "Is exposure balanced without muddy shadows or clipped highlights?",
            "Do skin tones and neutrals look believable (no gray/green/orange cast)?",
            "Is the edit visibly better than original at thumbnail size?",
            "Does crop improve composition rather than harming balance?",
            "Is sharpening clean (not crunchy) and contrast natural (not fake HDR)?",
        ],
        "rejection_criteria": [
            "Irrecoverable focus/composition/light quality issues.",
            "Subject remains muddy after reasonable RAW adjustments.",
            "Color remains fake or unstable after corrective refinement.",
            "Edit direction requires object removal or generative retouching.",
        ],
        "proof_only_criteria": [
            "Technical cleanup achieved but aesthetic strength still weak.",
            "Difference from original is valid but subtle and non-post-worthy.",
            "RawTherapee-only edits improve clarity but cannot create a strong final image.",
        ],
        "export_criteria": [
            "Preview is meaningfully better than original in exposure, color, and subject clarity.",
            "Core quality scores pass critique threshold with low overprocessing penalty.",
            "No obvious casts, muddy subject, fake HDR, or crunchy sharpening artifacts.",
        ],
        "style_specific_editing_priorities": style_priorities,
        "biggest_flaw_first_policy": (
            "Identify and fix the single biggest flaw first "
            "(usually subject exposure or color cast) before secondary styling."
        ),
        "what_to_avoid": [
            "Flattering mediocre results.",
            "Tiny invisible profile variations.",
            "Vague style adjectives without measurable improvements.",
            "Oversaturated phone-filter edits, fake HDR, crunchy sharpening.",
            "Muddy shadows, orange skin, gray/green casts.",
            "Matte/faded looks unless user explicitly requests them.",
        ],
        "rawtherapee_limitations": [
            "No generative fill/object removal.",
            "No true AI subject masks or semantic retouching.",
            "Complex local masking is limited compared to Lightroom/darktable advanced masking.",
        ],
        "llm_instructions": [
            "Do not flatter mediocre results.",
            "Do not export final unless the preview is meaningfully better than the original.",
            "Fix the biggest flaw first.",
            "Make the before/after difference visible at thumbnail size unless this is a subtle proof edit.",
            "If RawTherapee-only editing cannot solve the image, say so clearly.",
            "Prefer reject/proof_only over pretending every image is post-worthy.",
            "If subject or face remains muddy, do not call the image finished.",
            "If crop harms composition, revert crop or avoid crop.",
            "If color looks fake, reduce saturation/warmth and refine.",
        ],
    }

    if metadata:
        brief["metadata_context"] = metadata

    return brief


def editorial_candidate_parameters(style_name: str, style_family: str = "travel_portrait") -> dict[str, Any]:
    """Return candidate parameters for a named editorial style."""
    base = _STYLE_PARAMETERS.get(style_name, _STYLE_PARAMETERS["clean_editorial"])
    advanced_layers: list[dict[str, dict[str, Any]]] = []

    if style_name == "clean_editorial":
        advanced_layers = [
            gentle_s_curve(),
            clean_midtone_contrast(),
            reduce_green_gray_cast(),
            protect_skin_reduce_orange(),
            {
                "luminance_curve": {
                    "enabled": True,
                    "avoid_color_shift": True,
                    "red_skin_protection": 16,
                }
            },
        ]
    elif style_name == "warm_travel":
        advanced_layers = [
            gentle_s_curve(),
            warm_sand_preserve_skin(),
            soft_highlight_rolloff(),
            clean_sky_blue(),
            natural_green_control(),
            {
                "color_balance": {
                    "enabled": True,
                    "strength": 36,
                    "highlights_color_saturation": [62, 82],
                    "shadows_color_saturation": [74, 196],
                }
            },
        ]
    elif style_name == "cinematic_soft":
        advanced_layers = [
            cinematic_soft_color_separation(),
            reduce_green_gray_cast(),
            {
                "tone_curve": {"curve_mode2": "Standard", "curve2": "3;0;0.10;0.20;0.22;0.55;0.58;1;0.94;"},
                "luminance_curve": {
                    "enabled": True,
                    "contrast": -3,
                    "avoid_color_shift": True,
                    "lh_curve": "3;0;0;0.35;0.38;0.78;0.66;1;1;",
                    "hh_curve": "3;0;0;0.65;0.70;0.88;0.82;1;0.92;",
                },
            },
        ]

    combined = merge_parameter_sets(base, *advanced_layers)

    # Backlit/portrait-heavy families need stronger subject lift to avoid muddy faces.
    if style_family in {"travel_portrait", "portrait", "backlit_portrait"}:
        exposure_section = combined.get("exposure")
        exposure_values = exposure_section if isinstance(exposure_section, dict) else {}
        luminance_section = combined.get("luminance_curve")
        luminance_values = luminance_section if isinstance(luminance_section, dict) else {}
        adjusted = {
            **combined,
            "exposure": {
                **exposure_values,
                "compensation": float(exposure_values.get("compensation", 0.0)) + 0.15,
                "highlight_compression": int(exposure_values.get("highlight_compression", 20)) + 4,
            },
            "luminance_curve": {
                **luminance_values,
                "enabled": True,
                "contrast": 10 if style_name != "cinematic_soft" else 2,
            },
        }
        return adjusted

    return combined


def build_candidate_descriptor(style_name: str) -> dict[str, Any]:
    """Return narrative metadata for a candidate style."""
    return {
        "style_name": style_name,
        "intended_visual_effect": _CANDIDATE_EFFECTS.get(style_name, _CANDIDATE_EFFECTS["clean_editorial"]),
        "risks_to_check_in_preview": _CANDIDATE_RISKS.get(style_name, _CANDIDATE_RISKS["clean_editorial"]),
        "suggested_next_tools": ["preview_raw", "critique_gate", "adjust_profile"],
        "recommended_adjustment_strategy_if_it_fails": _CANDIDATE_FAIL_STRATEGIES.get(
            style_name,
            _CANDIDATE_FAIL_STRATEGIES["clean_editorial"],
        ),
    }


def build_critique_gate(
    preview_path: str | None,
    *,
    candidate_name: str,
    intended_style: str,
) -> dict[str, Any]:
    """Build a strict post-preview scoring contract for the LLM."""
    scoring_rubric = {
        "subject_separation_score": "0-10",
        "face_or_subject_exposure_score": "0-10",
        "composition_or_crop_score": "0-10",
        "tonal_separation_score": "0-10",
        "curve_quality_highlight_rolloff_score": "0-10",
        "skin_orange_control_score": "0-10",
        "green_grass_control_score": "0-10",
        "sky_blue_control_score": "0-10",
        "color_cast_score": "0-10",
        "phone_filter_penalty": "0-10",
        "muddy_shadows_penalty": "0-10",
        "basic_adjustment_penalty": "0-10",
        "mood_match_score": "0-10",
        "professional_polish_score": "0-10",
        "overprocessing_penalty": "0-10",
        "post_worthy_verdict": "export | refine | proof_only | reject",
        "next_action": "One-sentence concrete next step",
    }

    return {
        "preview_path": preview_path,
        "candidate_name": candidate_name,
        "intended_style": intended_style,
        "scoring_rubric": scoring_rubric,
        "minimum_export_threshold": {
            "core_score_average_min": 7.0,
            "overprocessing_penalty_max": 3,
            "verdict_required": "export",
        },
        "automatic_failure_conditions": [
            "Subject/face is still too dark or muddy.",
            "Colors look fake (orange skin, gray/green cast, oversaturated filter look).",
            "Grass/foliage is neon or skies look synthetic/cyan-heavy.",
            "Crop worsens composition or removes critical context.",
            "Edit feels barely different from original while output goal is post_worthy.",
            "Edit only shifts exposure/warmth/saturation without tonal/color separation.",
            "Sharpening/contrast artifacts look crunchy or fake HDR.",
        ],
        "required_llm_answers": [
            "What is the single biggest flaw in this candidate?",
            "Is the difference from original clearly visible at thumbnail size?",
            "What curve/color-separation decisions are visible (or missing)?",
            "Does this look like a basic phone filter? Why or why not?",
            "Does this candidate pass export threshold? If not, why exactly?",
            "What precise adjustment should be applied next (or reject/proof_only)?",
        ],
        "next_action_rules": [
            "If the edit only changes exposure/warmth/saturation and still looks basic, mark refine.",
            "If subject/face is still too dark or muddy, do not export final.",
            "If edit is only slightly different and output_goal is post_worthy, verdict must be refine.",
            "If skin is orange or grass is neon, do not export.",
            "If cinematic_soft becomes gray/green and flat, mark refine or reject.",
            "If tonal separation is weak, refine using curves or color-balance tools before export.",
            "If crop makes composition worse, revert crop or try another crop.",
            "If colors look fake, reduce saturation/warmth and refine.",
            "If image cannot become post-worthy with RawTherapee-only edits, mark proof_only or reject.",
            "If total score is below threshold, do not process final. Use adjust_profile or mark proof/reject.",
            "Do not praise the edit unless it clears threshold.",
            "Do not use words like stunning, perfect, or professional unless score supports it.",
        ],
        "adjustment_guidance": {
            "priority_order": [
                "fix_subject_exposure",
                "neutralize_color_cast",
                "build_tonal_separation_with_curves",
                "separate_warm_cool_color_balance",
                "protect_skin_and_tame_greens_blues",
                "repair_crop_or_composition",
                "refine_contrast_saturation_sharpening",
            ],
            "when_to_stop": "Stop refining when threshold is passed without overprocessing artifacts.",
        },
        "final_instruction": (
            "Use this gate as a contract: score honestly, reject weak edits, "
            "and export only when threshold is truly met."
        ),
    }


def build_curation_plan(
    directory: str,
    *,
    intent: str | None,
    recursive: bool,
    max_files: int | None,
    discovered_files: list[str] | None = None,
) -> dict[str, Any]:
    """Build an opinionated directory-level curation workflow."""
    return {
        "directory": directory,
        "intent": intent,
        "recursive": recursive,
        "max_files": max_files,
        "discovered_file_count": len(discovered_files or []),
        "workflow_steps": [
            "Scan RAW files and do a quick technical triage preview.",
            "Classify each file into reject, proof_only, edit_candidate, or strong_keeper.",
            "Run full editorial candidate workflow only for strong_keeper files.",
            "Use proof_only export for salvageable files that fail post-worthy threshold.",
            "Avoid editing every file by default; be selective.",
        ],
        "rating_categories": {
            "reject": "Weak composition/focus/light; not worth full edit cycle.",
            "proof_only": "Technically recoverable but not strong enough for posting.",
            "edit_candidate": "Promising but requires more work before keeper status.",
            "strong_keeper": "Clear potential for post-worthy final after editorial loop.",
        },
        "suggested_batch_prompt": (
            "Be strict: classify each RAW as reject/proof_only/edit_candidate/strong_keeper. "
            "Only run generate_editorial_candidates on strong_keeper files."
        ),
        "export_policy": [
            "Do not export finals for reject files.",
            "Proof-only exports are allowed for documentation/reference.",
            "Final exports require critique_gate threshold pass.",
        ],
        "reminder": "Weak photos should not be forced into post-worthy exports.",
    }


def ensure_existing_file(file_path: str) -> Path:
    """Validate file path exists and return a Path object."""
    path = Path(file_path)
    if not path.is_file():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)
    return path
