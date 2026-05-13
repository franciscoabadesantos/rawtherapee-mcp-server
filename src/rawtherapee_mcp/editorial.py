"""Opinionated editorial workflow helpers for autonomous RAW editing guidance."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rawtherapee_mcp.advanced_color import (
    clean_midtone_contrast,
    clean_sky_blue,
    gentle_s_curve,
    merge_parameter_sets,
    natural_green_control,
    protect_skin_reduce_orange,
    reduce_green_gray_cast,
    soft_highlight_rolloff,
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
    "create_editing_vision",
    "create_editorial_brief",
    "generate_vision_candidates or generate_editorial_candidates",
    "preview_raw or preview_before_after",
    "critique_gate",
    "adjust_profile or refine using visual moves (only when critique says refine)",
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
        "microcontrast": {"enabled": True, "strength": 18},
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
        "microcontrast": {"enabled": True, "strength": 20},
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
        "microcontrast": {"enabled": True, "strength": 15},
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

_LIKELY_INTENT_CATEGORIES = [
    "clean_portrait",
    "environmental_portrait",
    "casual_memory",
    "atmosphere_memory",
    "travel_place_vibe",
    "landscape_light",
    "object_detail",
    "architecture_geometry",
    "event_documentary",
    "party_energy",
    "wedding_or_formal_event",
    "food_or_product",
    "street_moment",
    "funny_situation",
    "rain_melancholy",
    "neon_nightlife",
    "sunset_silhouette",
    "beach_summer",
    "studio_polished",
    "proof_only",
]

_PORTRAIT_CRITICAL_CATEGORIES = {
    "clean_portrait",
    "studio_polished",
    "wedding_or_formal_event",
    "food_or_product",
}

_AMBIENCE_FORWARD_CATEGORIES = {
    "sunset_silhouette",
    "atmosphere_memory",
    "rain_melancholy",
    "neon_nightlife",
}

_PLACE_EVENT_CATEGORIES = {
    "travel_place_vibe",
    "landscape_light",
    "event_documentary",
    "party_energy",
    "street_moment",
    "beach_summer",
}


def safe_slug(value: str, fallback: str = "profile") -> str:
    """Convert free text into a path-safe slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-._")
    return cleaned or fallback


def _normalized_words(value: str) -> set[str]:
    """Return lowercase token words for fuzzy intent matching."""
    return {part for part in re.split(r"[^a-z0-9]+", value.lower()) if part}


def _string_list(value: object) -> list[str]:
    """Convert unknown values into a list of non-empty strings."""
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    output.append(cleaned)
        return output
    return []


def _parse_rt_major_minor(rt_version: str | None) -> tuple[int, int] | None:
    """Extract RawTherapee major/minor version numbers from CLI output."""
    if not rt_version:
        return None

    match = re.search(r"(\d+)\.(\d+)", rt_version)
    if not match:
        return None

    return int(match.group(1)), int(match.group(2))


def _sanitize_microcontrast(
    parameters: dict[str, Any],
    *,
    rt_version: str | None = None,
) -> dict[str, Any]:
    """Normalize microcontrast keys and avoid RT 5.10 artifact-prone settings."""
    section = parameters.get("microcontrast")
    if not isinstance(section, dict):
        return parameters

    micro = dict(section)
    if "strength" in micro and "amount" not in micro:
        micro["amount"] = micro.pop("strength")
    micro.setdefault("contrast", 20)

    version = _parse_rt_major_minor(rt_version)
    if version == (5, 10):
        # RT 5.10 rendered severe white posterization in previews when
        # editorial candidates used high SharpenMicro uniformity values.
        micro["enabled"] = False
        micro.pop("uniformity", None)

    updated = dict(parameters)
    updated["microcontrast"] = micro
    return updated


def _resolve_intent_categories(inferred_intent: dict[str, Any] | None, intent: str | None) -> list[str]:
    """Collect and normalize intent categories from multiple optional sources."""
    collected: list[str] = []
    if intent:
        collected.extend(_string_list(intent))
    if inferred_intent:
        collected.extend(_string_list(inferred_intent.get("primary_intent_category")))
        collected.extend(_string_list(inferred_intent.get("selected_intent_category")))
        collected.extend(_string_list(inferred_intent.get("likely_intent_categories")))
        collected.extend(_string_list(inferred_intent.get("secondary_intent_categories")))

    normalized_known: list[str] = []
    seen: set[str] = set()
    known = set(_LIKELY_INTENT_CATEGORIES)
    for raw in collected:
        slug = safe_slug(raw, fallback="")
        if not slug:
            continue
        if slug in known and slug not in seen:
            normalized_known.append(slug)
            seen.add(slug)
            continue

        words = _normalized_words(raw)
        if {"sunset", "silhouette"} & words:
            mapped = "sunset_silhouette"
        elif {"studio", "polished"} & words:
            mapped = "studio_polished"
        elif {"neon", "nightlife"} & words:
            mapped = "neon_nightlife"
        elif {"travel", "place"} & words:
            mapped = "travel_place_vibe"
        elif {"documentary", "event"} & words:
            mapped = "event_documentary"
        elif {"atmosphere", "ambience", "ambient", "mood"} & words:
            mapped = "atmosphere_memory"
        elif {"portrait", "face"} & words:
            mapped = "clean_portrait"
        elif {"proof"} & words:
            mapped = "proof_only"
        elif {"rain", "melancholy"} & words:
            mapped = "rain_melancholy"
        else:
            mapped = ""

        if mapped and mapped not in seen:
            normalized_known.append(mapped)
            seen.add(mapped)

    return normalized_known


def _build_intent_standard(inferred_intent: dict[str, Any] | None, intent: str | None) -> dict[str, Any]:
    """Translate inferred categories into critique/brief rules."""
    categories = _resolve_intent_categories(inferred_intent, intent)
    primary = categories[0] if categories else "clean_portrait"

    if primary in _PORTRAIT_CRITICAL_CATEGORIES:
        return {
            "primary_intent_category": primary,
            "matched_categories": categories,
            "subject_clarity_priority": "critical",
            "dark_subject_policy": "Dark/muddy face is usually a serious failure.",
            "preserve_even_if_imperfect": [
                "Natural skin texture and believable color.",
                "Authentic scene lighting if it still supports clear subject readability.",
            ],
            "do_not_fix_away": [
                "Natural skin texture through excessive smoothing.",
                "Facial shape realism via heavy tone manipulation.",
            ],
            "avoid_overcorrections": [
                "Do not chase stylization before subject exposure and skin neutrality are solved.",
                "Do not hide weak subject clarity with heavy contrast or saturation.",
            ],
            "critique_focus": [
                "Subject/face readability",
                "Skin and neutral color fidelity",
                "Clean tonal polish without crunchy artifacts",
            ],
        }

    if primary in _AMBIENCE_FORWARD_CATEGORIES:
        return {
            "primary_intent_category": primary,
            "matched_categories": categories,
            "subject_clarity_priority": "contextual",
            "dark_subject_policy": (
                "Dark/partial silhouette can be intentional if mood and readability remain believable."
            ),
            "preserve_even_if_imperfect": [
                "Warm or cool ambience that carries the scene mood.",
                "Intentional darkness, low-key contrast, and end-of-day atmosphere.",
            ],
            "do_not_fix_away": [
                "Mood-defining color cast or darkness that makes the scene feel authentic.",
                "Partial silhouette that supports atmosphere.",
            ],
            "avoid_overcorrections": [
                "Do not force bright portrait standards on ambience-first scenes.",
                "Do not neutralize neon/night color casts when they are the point.",
            ],
            "critique_focus": [
                "Mood and intent alignment",
                "Believable darkness and highlight rolloff",
                "Readability without killing ambience",
            ],
        }

    if primary in _PLACE_EVENT_CATEGORIES:
        return {
            "primary_intent_category": primary,
            "matched_categories": categories,
            "subject_clarity_priority": "balanced",
            "dark_subject_policy": (
                "Judge darkness against place/event storytelling value, not portrait-only standards."
            ),
            "preserve_even_if_imperfect": [
                "Place atmosphere and lighting character.",
                "Moment authenticity, timing, and narrative context.",
            ],
            "do_not_fix_away": [
                "Scene context through over-cropping or aggressive tonal cleanup.",
                "Authentic color mood that communicates location/event energy.",
            ],
            "avoid_overcorrections": [
                "Do not over-style documentary/travel frames into fake HDR or phone-filter aesthetics.",
                "Do not prioritize technical cleanliness over the reason the frame works.",
            ],
            "critique_focus": [
                "Place/event authenticity",
                "Color/tonal separation with believable realism",
                "Context preservation in crop and contrast decisions",
            ],
        }

    return {
        "primary_intent_category": primary,
        "matched_categories": categories,
        "subject_clarity_priority": "balanced",
        "dark_subject_policy": "Balance subject readability with ambience; avoid one-size-fits-all scoring.",
        "preserve_even_if_imperfect": [
            "Scene mood and context.",
            "Natural color relationships.",
        ],
        "do_not_fix_away": [
            "The visual reason the photo was taken.",
        ],
        "avoid_overcorrections": [
            "Do not over-correct until the image loses authenticity.",
        ],
        "critique_focus": [
            "Intent alignment",
            "Believability",
            "Technical quality proportional to intent",
        ],
    }


def build_intent_inference_contract(
    file_path: str,
    *,
    user_intent: str | None = None,
    context_hint: str | None = None,
) -> dict[str, Any]:
    """Return a structured intent-inference contract for LLM visual reasoning."""
    return {
        "file_path": file_path,
        "user_intent": user_intent,
        "context_hint": context_hint,
        "required_visual_questions": [
            "What is the likely reason this photo exists?",
            "What is the emotional or visual payoff?",
            (
                "Is the main value subject clarity, ambience, light, place, geometry, humor, "
                "event memory, or object detail?"
            ),
            "What should be preserved even if technically imperfect?",
            "What should not be corrected away?",
            "What would make the edit feel fake or contrary to the scene?",
            "What critique standard should critique_gate use for this frame?",
        ],
        "likely_intent_categories": list(_LIKELY_INTENT_CATEGORIES),
        "intent_model_schema": {
            "primary_intent_category": "one of likely_intent_categories (or a custom compatible label)",
            "secondary_intent_categories": ["optional secondary categories"],
            "scene_value_priority": [
                "subject_clarity",
                "ambience",
                "light",
                "place",
                "geometry",
                "humor",
                "event_memory",
                "object_detail",
            ],
            "emotional_payoff": "1-2 sentence explanation of what should be felt",
            "preservation_targets": ["what to preserve even if imperfect"],
            "anti_fixes": ["what not to 'fix away'"],
            "editing_strategy": ["directional editing rules for this image"],
            "critique_standard": {
                "subject_clarity_priority": "critical | balanced | contextual",
                "dark_subject_policy": "when dark subjects are acceptable vs failure",
                "authenticity_priority": "low | medium | high",
            },
            "confidence": "low | medium | high",
        },
        "preservation_targets": [
            "Intentional mood, color cast, and lighting character.",
            "Scene context and narrative reason for the photo.",
            "Natural-looking tonal relationships that still feel like the captured moment.",
        ],
        "possible_anti_fixes": [
            "Over-lifting ambience shots into flat bright portraits.",
            "Neutralizing neon/night color casts that are central to the vibe.",
            "Over-cleaning documentary/travel frames until they lose authenticity.",
        ],
        "editing_strategy_guidance": [
            "Infer intent from preview first, then pick style and candidate adjustments.",
            "Treat technical perfection as context-dependent, not universal.",
            "Preserve the reason the image works before polishing secondary issues.",
        ],
        "critique_standard_guidance": [
            "Use strict face/subject clarity standards for clean portrait or studio-polished goals.",
            "Allow intentional darkness and partial silhouette for sunset/atmosphere intent.",
            "For documentary/travel intent, prioritize authenticity and scene value over cosmetic cleanup.",
            "For neon nightlife, preserve color separation and avoid forced neutral white balance.",
        ],
        "output_contract": {
            "precondition": (
                "If visual inspection has not happened in this session, call preview_raw first and inspect the image "
                "before filling this intent model."
            ),
            "required_fields": [
                "primary_intent_category",
                "emotional_payoff",
                "preservation_targets",
                "anti_fixes",
                "editing_strategy",
                "critique_standard",
            ],
            "response_format": "Return JSON-like structured values so downstream tools can consume them.",
        },
        "next_recommended_tools": [
            "preview_raw",
            "create_editing_vision",
            "create_editorial_brief",
            "generate_editorial_candidates",
            "critique_gate",
        ],
    }


def build_editorial_brief(
    file_path: str,
    *,
    intent: str | None,
    style: str,
    output_goal: str,
    inferred_intent: dict[str, Any] | None = None,
    editing_vision: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict editing brief for the LLM's editorial loop."""
    normalized_style = style if style in SUPPORTED_EDITORIAL_STYLES else "clean_editorial"
    style_priorities = _STYLE_PRIORITIES.get(normalized_style, _STYLE_PRIORITIES["clean_editorial"])
    intent_standard = _build_intent_standard(inferred_intent, intent)
    subject_priority = str(intent_standard.get("subject_clarity_priority", "balanced"))

    visual_checklist = [
        "Is exposure balanced without muddy shadows or clipped highlights?",
        "Do skin tones and neutrals look believable (no gray/green/orange cast)?",
        "Is the edit visibly better than original at thumbnail size?",
        "Does crop improve composition rather than harming balance?",
        "Is sharpening clean (not crunchy) and contrast natural (not fake HDR)?",
        "Does the edit preserve the reason this photo works?",
    ]
    if subject_priority == "critical":
        visual_checklist.insert(0, "Is subject/face clearly visible and separated from background?")
    else:
        visual_checklist.insert(0, "If subject is dark, is that darkness intentional and still readable enough?")

    rejection_criteria = [
        "Irrecoverable focus/composition/light quality issues.",
        "Color remains fake or unstable after corrective refinement.",
        "Edit direction requires object removal or generative retouching.",
        "Edit corrects away the reason the photo works.",
    ]
    if subject_priority == "critical":
        rejection_criteria.insert(1, "Subject remains muddy after reasonable RAW adjustments.")
    else:
        rejection_criteria.insert(
            1,
            "Subject readability is unintentionally muddy and no longer supports the intended mood or story.",
        )

    export_criteria = [
        "Core quality scores pass critique threshold with low overprocessing penalty.",
        "No obvious casts, fake HDR, or crunchy sharpening artifacts.",
        "Result stays aligned with inferred intent and preserves scene value.",
    ]
    if subject_priority == "critical":
        export_criteria.insert(
            0,
            "Preview is meaningfully better than original in exposure, color, and subject clarity.",
        )
    else:
        export_criteria.insert(
            0,
            "Preview is meaningfully better than original while preserving ambience, place, or event value.",
        )

    llm_instructions = [
        "Do not flatter mediocre results.",
        "Do not export final unless the preview is meaningfully better than the original.",
        "Fix the biggest flaw first.",
        "Make the before/after difference visible at thumbnail size unless this is a subtle proof edit.",
        "If RawTherapee-only editing cannot solve the image, say so clearly.",
        "Prefer reject/proof_only over pretending every image is post-worthy.",
        "If crop harms composition, revert crop or avoid crop.",
        "If color looks fake, reduce saturation/warmth and refine.",
        "Do not force one universal standard; score against inferred intent.",
        "If edits remove the reason this photo works, mark refine or reject.",
    ]
    if subject_priority == "critical":
        llm_instructions.insert(6, "If subject or face remains muddy, do not call the image finished.")
    else:
        llm_instructions.insert(
            6,
            "For ambience-first scenes, do not over-lift intentional darkness just to mimic bright portrait standards.",
        )

    brief: dict[str, Any] = {
        "file_path": file_path,
        "intent": intent,
        "inferred_intent": inferred_intent,
        "intent_standard": intent_standard,
        "style": normalized_style,
        "output_goal": output_goal,
        "recommended_workflow": [
            "preview_raw",
            "infer_photo_intent",
            "create_editing_vision",
            *_DEFAULT_RECOMMENDED_WORKFLOW,
        ],
        "required_preview_loop_steps": [
            "Generate at least 3 distinct candidates before selecting a direction.",
            "Preview each candidate and compare against original at thumbnail size.",
            "Run critique_gate after every preview and follow its verdict strictly.",
            "Refine the biggest flaw first, then re-preview before any export decision.",
            "If inferred intent changes after preview, revise the brief and critique standard.",
        ],
        "visual_critique_checklist": visual_checklist,
        "rejection_criteria": rejection_criteria,
        "proof_only_criteria": [
            "Technical cleanup achieved but aesthetic strength still weak.",
            "Difference from original is valid but subtle and non-post-worthy.",
            "RawTherapee-only edits improve clarity but cannot create a strong final image.",
        ],
        "export_criteria": export_criteria,
        "style_specific_editing_priorities": style_priorities,
        "intent_preservation_targets": intent_standard["preserve_even_if_imperfect"],
        "intent_anti_fixes": intent_standard["do_not_fix_away"],
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
        "llm_instructions": llm_instructions,
    }

    if metadata:
        brief["metadata_context"] = metadata

    if editing_vision:
        vision_preserve = _string_list(editing_vision.get("preserve"))
        vision_avoid = _string_list(editing_vision.get("avoid"))
        if vision_preserve:
            brief["intent_preservation_targets"] = [
                *brief["intent_preservation_targets"],
                *vision_preserve,
            ]
            brief["export_criteria"].append("Preserves the editing-vision anchor, mood, and preservation targets.")
        if vision_avoid:
            brief["what_to_avoid"] = [*brief["what_to_avoid"], *vision_avoid]
        brief["editing_vision"] = editing_vision
        brief["visual_intention_priority"] = [
            "Strengthen the chosen visual anchor before chasing broad stylization.",
            "Deemphasize distractions rather than globally brightening or sharpening everything.",
            "Reject edits that feel like generic presets instead of serving the image's vision.",
        ]

    return brief


def editorial_candidate_parameters(
    style_name: str,
    style_family: str = "travel_portrait",
    *,
    inferred_intent: dict[str, Any] | None = None,
    style_direction: str | None = None,
    rt_version: str | None = None,
) -> dict[str, Any]:
    """Return candidate parameters for a named editorial style."""
    base = _sanitize_microcontrast(
        _STYLE_PARAMETERS.get(style_name, _STYLE_PARAMETERS["clean_editorial"]),
        rt_version=rt_version,
    )
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
            soft_highlight_rolloff(),
            protect_skin_reduce_orange(),
            clean_sky_blue(),
            natural_green_control(),
        ]
    elif style_name == "cinematic_soft":
        advanced_layers = [
            gentle_s_curve(),
            soft_highlight_rolloff(),
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

    intent_standard = _build_intent_standard(inferred_intent, style_direction)
    primary_intent = str(intent_standard.get("primary_intent_category", "clean_portrait"))
    effective_style_family = style_family

    if primary_intent in _AMBIENCE_FORWARD_CATEGORIES:
        effective_style_family = "landscape"
    elif primary_intent in _PORTRAIT_CRITICAL_CATEGORIES:
        effective_style_family = "portrait"

    # Backlit/portrait-heavy families need stronger subject lift to avoid muddy faces.
    if effective_style_family in {"travel_portrait", "portrait", "backlit_portrait"}:
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
        combined = adjusted

    if primary_intent in _AMBIENCE_FORWARD_CATEGORIES:
        exposure_section = combined.get("exposure")
        exposure_values = exposure_section if isinstance(exposure_section, dict) else {}
        white_balance_section = combined.get("white_balance")
        white_balance_values = white_balance_section if isinstance(white_balance_section, dict) else {}
        if style_name == "cinematic_soft":
            return {
                **combined,
                "exposure": {
                    **exposure_values,
                    "compensation": max(-0.05, float(exposure_values.get("compensation", 0.0)) - 0.18),
                    "highlight_compression": int(exposure_values.get("highlight_compression", 24)) + 6,
                },
                "white_balance": {
                    **white_balance_values,
                    "temperature": int(white_balance_values.get("temperature", 5600)) + 250,
                },
            }
        return combined

    if primary_intent in _PORTRAIT_CRITICAL_CATEGORIES and style_name in {"clean_editorial", "warm_travel"}:
        exposure_section = combined.get("exposure")
        exposure_values = exposure_section if isinstance(exposure_section, dict) else {}
        return {
            **combined,
            "exposure": {
                **exposure_values,
                "compensation": float(exposure_values.get("compensation", 0.0)) + 0.08,
            },
        }

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
    inferred_intent: dict[str, Any] | None = None,
    critique_standard: dict[str, Any] | str | None = None,
    editing_vision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict post-preview scoring contract for the LLM."""
    merged_intent: dict[str, Any] | None = None
    if isinstance(critique_standard, dict):
        merged_intent = critique_standard
    elif isinstance(inferred_intent, dict):
        merged_intent = inferred_intent

    intent_hint = critique_standard if isinstance(critique_standard, str) else None
    intent_standard = _build_intent_standard(merged_intent, intent_hint)
    subject_priority = str(intent_standard.get("subject_clarity_priority", "balanced"))
    dark_subject_policy = str(intent_standard.get("dark_subject_policy", ""))

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
        "intent_alignment_score": "0-10",
        "preserved_scene_value_score": "0-10",
        "visual_anchor_score": "0-10",
        "emotional_goal_score": "0-10",
        "preservation_score": "0-10",
        "distraction_control_score": "0-10",
        "generic_preset_penalty": "0-10",
        "vision_alignment_score": "0-10",
        "harmful_overcorrection_penalty": "0-10",
        "visual_anchor_score": "0-10",
        "emotional_goal_score": "0-10",
        "preservation_score": "0-10",
        "distraction_control_score": "0-10",
        "generic_preset_penalty": "0-10",
        "vision_alignment_score": "0-10",
        "artifact_penalty": "0-10",
        "wrong_standard_warning": "true|false with one-sentence reason",
        "overprocessing_penalty": "0-10",
        "post_worthy_verdict": "export | refine | proof_only | reject",
        "next_action": "One-sentence concrete next step",
    }

    automatic_failure_conditions = [
        "Colors look fake (orange skin, gray/green cast, oversaturated filter look).",
        "Grass/foliage is neon or skies look synthetic/cyan-heavy.",
        "Crop worsens composition or removes critical context.",
        "Edit feels barely different from original while output goal is post_worthy.",
        "Edit only shifts exposure/warmth/saturation without tonal/color separation.",
        "Sharpening/contrast artifacts look crunchy or fake HDR.",
        "Edit corrects away the reason the photo works.",
    ]
    if subject_priority == "critical":
        automatic_failure_conditions.insert(0, "Subject/face is still too dark or muddy for this intent.")
    else:
        automatic_failure_conditions.insert(
            0,
            "Dark subject is judged as failure only when it breaks intended readability for this scene.",
        )

    next_action_rules = [
        "If the edit only changes exposure/warmth/saturation and still looks basic, mark refine.",
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
        "If wrong_standard_warning is true, revise critique standard before final verdict.",
        "If harmful_overcorrection_penalty is high, revert toward scene-authentic values.",
        "If the edit removes the visual reason this photo exists, mark refine or reject.",
        "If artifacts appear (posterization, halos, contour speckling), mark refine or reject.",
    ]
    if subject_priority == "critical":
        next_action_rules.insert(1, "If subject/face is still too dark or muddy, do not export final.")
    else:
        next_action_rules.insert(
            1,
            "Do not force bright portrait exposure when ambience/silhouette intent is primary.",
        )

    vision_questions = [
        "Did this edit serve the visual anchor?",
        "Did this preserve the emotional goal?",
        "What preservation target was protected most clearly?",
        "What distraction was reduced or still unresolved?",
        "Does this look like a generic preset or an image-specific edit?",
        "Were any artifacts introduced?",
    ]

    if editing_vision:
        next_action_rules.extend(
            [
                "Prioritize alignment to visual_anchor over generic style labels.",
                "If emotional goal is not visible, verdict cannot be export.",
                "If preserve targets were compromised, revert and refine before export.",
            ]
        )

    return {
        "preview_path": preview_path,
        "candidate_name": candidate_name,
        "intended_style": intended_style,
        "inferred_intent": inferred_intent,
        "critique_standard": critique_standard,
        "editing_vision": editing_vision,
        "intent_standard": intent_standard,
        "dark_subject_policy": dark_subject_policy,
        "scoring_rubric": scoring_rubric,
        "minimum_export_threshold": {
            "core_score_average_min": 7.0,
            "overprocessing_penalty_max": 3,
            "verdict_required": "export",
        },
        "automatic_failure_conditions": automatic_failure_conditions,
        "required_llm_answers": [
            "What inferred intent category is this critique using and why?",
            "What is the single biggest flaw in this candidate?",
            "Is the difference from original clearly visible at thumbnail size?",
            "What curve/color-separation decisions are visible (or missing)?",
            "Does this look like a basic phone filter? Why or why not?",
            "Did this edit preserve the scene value and emotional payoff?",
            "Did the edit strengthen the visual anchor?",
            "Did it preserve the emotional goal instead of replacing it with a generic preset look?",
            "What distractions were reduced or left competing?",
            "Did it destroy anything the image needed to preserve?",
            "Were any artifacts or rendering failures introduced?",
            "Did any correction remove the reason the photo works?",
            "Does this candidate pass export threshold? If not, why exactly?",
            "What precise adjustment should be applied next (or reject/proof_only)?",
            *vision_questions,
        ],
        "next_action_rules": next_action_rules,
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
            "intent_guidance": {
                "clean_portrait_or_studio_polished": (
                    "Prioritize face/subject clarity and skin realism; dark muddy subject is usually a serious failure."
                ),
                "sunset_silhouette_or_atmosphere_memory": (
                    "Darkness, warm cast, and partial silhouette can be intentional; "
                    "preserve mood and avoid over-lifting."
                ),
                "event_documentary": "Moment and authenticity can outweigh perfect lighting.",
                "neon_nightlife": "Strong color casts can be the point; avoid forced neutralization.",
                "rain_melancholy": "Do not erase mood by over-brightening.",
                "travel_place_vibe": "Preserve place ambience and context, not just subject correction.",
            },
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
