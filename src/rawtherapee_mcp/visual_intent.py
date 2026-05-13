"""Vision-first editing helpers built around safe high-level visual moves."""

from __future__ import annotations

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

ParameterSet = dict[str, dict[str, Any]]

_VALID_INTENSITIES = ("low", "medium", "high")
_INTENSITY_SCALE = {"low": 0.7, "medium": 1.0, "high": 1.25}
_MOVE_NAMES = (
    "emphasize_subject",
    "preserve_silhouette",
    "shape_light_break",
    "deepen_cloud_weight",
    "soften_mist",
    "enhance_water_depth",
    "increase_color_presence",
    "warm_memory",
    "cool_melancholy",
    "reduce_distractions",
    "enhance_geometry",
    "protect_skin",
    "natural_greens",
    "clean_sky",
    "lift_readability",
    "deepen_clean_shadows",
    "soft_highlight_rolloff",
    "gentle_tonal_separation",
    "calm_phone_filter_look",
    "preserve_event_authenticity",
)
_VISUAL_ANCHOR_OPTIONS = [
    "face or primary subject",
    "light break or brightest storytelling area",
    "ocean or water mass",
    "cloud structure or atmosphere",
    "architecture or geometry",
    "place context or environmental storytelling",
    "gesture, moment, or event interaction",
]
_EMOTIONAL_GOAL_OPTIONS = [
    "clean and believable",
    "mysterious but hopeful",
    "warm memory",
    "cool melancholy",
    "quiet atmospheric depth",
    "documentary authenticity",
    "graphic clarity and structure",
]
_DEFAULT_VISION_MOVES = [
    "gentle_tonal_separation",
    "soft_highlight_rolloff",
    "reduce_distractions",
]
_SAFE_MOVE_NOTES = [
    "No RawTherapee ColorToning / split-toning defaults are used.",
    "No SharpenMicro Uniformity is emitted.",
    "No Locallab mask preview or unstable local preview flags are emitted.",
    "Tone and color moves stay in small, editorial-safe ranges.",
]
_FAITHFUL_SUPPORT_MOVES = ("reduce_distractions", "soft_highlight_rolloff", "gentle_tonal_separation")
_EXPRESSIVE_SUPPORT_MOVES = ("increase_color_presence", "deepen_clean_shadows", "lift_readability")
_EXPERIMENT_SUPPORT_MOVES = ("shape_light_break", "deepen_cloud_weight", "enhance_water_depth", "warm_memory")


def _string_list(value: object) -> list[str]:
    """Convert unknown input into a cleaned string list."""
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, list):
        cleaned_values: list[str] = []
        for item in value:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    cleaned_values.append(cleaned)
        return cleaned_values
    return []


def _normalize_intensity(intensity: str) -> str:
    """Return a supported intensity label."""
    return intensity if intensity in _VALID_INTENSITIES else "medium"


def _scale(value: float | int, intensity: str) -> float:
    """Scale a move magnitude by the selected intensity."""
    return float(value) * _INTENSITY_SCALE[_normalize_intensity(intensity)]


def _round_int(value: float | int) -> int:
    """Round a numeric value to int for PP3 integer fields."""
    return int(round(float(value)))


def _clamp(value: float | int, lower: float, upper: float) -> float:
    """Clamp numeric value to a safe interval."""
    return max(lower, min(upper, float(value)))


def _merge_move_layers(layers: list[ParameterSet]) -> ParameterSet:
    """Merge multiple parameter layers safely."""
    if not layers:
        return {}
    return merge_parameter_sets(*layers)


def _curve_for_mist(intensity: str) -> str:
    """Gentle curve that softens contrast without flattening the image."""
    if _normalize_intensity(intensity) == "high":
        return "3;0;0.02;0.25;0.23;0.52;0.53;0.80;0.82;1;0.97;"
    if _normalize_intensity(intensity) == "low":
        return "3;0;0.00;0.25;0.24;0.50;0.51;0.78;0.83;1;1.00;"
    return "3;0;0.01;0.25;0.24;0.51;0.52;0.79;0.83;1;0.98;"


def _move_parameters(move_name: str, intensity: str, intent_profile: dict[str, Any] | None) -> ParameterSet:
    """Translate one high-level visual move into safe PP3 parameter groups."""
    profile = intent_profile or {}
    scale = _INTENSITY_SCALE[_normalize_intensity(intensity)]
    primary_intent = str(profile.get("primary_intent_category", ""))
    portrait_like = primary_intent in {"clean_portrait", "studio_polished", "wedding_or_formal_event"}

    if move_name == "emphasize_subject":
        return {
            "exposure": {
                "compensation": round(_scale(0.18, intensity), 2),
                "contrast": _round_int(_scale(4, intensity)),
            },
            "luminance_curve": {
                "enabled": True,
                "contrast": _round_int(_scale(6, intensity)),
                "avoid_color_shift": True,
                "red_skin_protection": 12 if portrait_like else 8,
            },
        }
    if move_name == "preserve_silhouette":
        return {
            "exposure": {
                "compensation": round(_clamp(_scale(-0.05, intensity), -0.15, 0.02), 2),
                "highlight_compression": _round_int(_clamp(_scale(18, intensity), 12, 28)),
                "black": _round_int(_clamp(_scale(-3, intensity), -5, -1)),
            }
        }
    if move_name == "shape_light_break":
        return merge_parameter_sets(
            soft_highlight_rolloff(),
            {
                "exposure": {
                    "compensation": round(_clamp(_scale(0.12, intensity), 0.06, 0.24), 2),
                    "highlight_compression": _round_int(_clamp(_scale(24, intensity), 18, 34)),
                },
                "luminance_curve": {
                    "enabled": True,
                    "contrast": _round_int(_clamp(_scale(4, intensity), 2, 7)),
                    "avoid_color_shift": True,
                    "lh_curve": "3;0;0;0.35;0.40;0.70;0.64;1;1;",
                    "hh_curve": "3;0;0;0.60;0.68;0.86;0.80;1;0.93;",
                },
            },
        )
    if move_name == "deepen_cloud_weight":
        return merge_parameter_sets(
            gentle_s_curve(),
            {
                "exposure": {
                    "contrast": _round_int(_clamp(_scale(5, intensity), 3, 8)),
                    "highlight_compression": _round_int(_clamp(_scale(20, intensity), 14, 30)),
                    "black": _round_int(_clamp(_scale(-4, intensity), -6, -2)),
                    "saturation": _round_int(_clamp(_scale(-1, intensity), -2, 0)),
                }
            },
        )
    if move_name == "soften_mist":
        return {
            "exposure": {
                "contrast": _round_int(_clamp(_scale(-2, intensity), -4, -1)),
                "highlight_compression": _round_int(_clamp(_scale(14, intensity), 8, 22)),
            },
            "tone_curve": {
                "curve_mode": "Standard",
                "curve_mode2": "Standard",
                "curve2": _curve_for_mist(intensity),
            },
            "sharpening": {
                "enabled": True,
                "radius": 0.45,
                "amount": _round_int(_clamp(110 + 10 * scale, 105, 125)),
            },
            "noise_reduction": {
                "enabled": True,
                "luminance": _round_int(_clamp(10 + 2 * scale, 10, 14)),
                "chrominance": _round_int(_clamp(10 + 2 * scale, 10, 14)),
            },
        }
    if move_name == "enhance_water_depth":
        return merge_parameter_sets(
            clean_sky_blue(),
            {
                "exposure": {
                    "contrast": _round_int(_clamp(_scale(3, intensity), 2, 5)),
                    "black": _round_int(_clamp(_scale(-2, intensity), -3, -1)),
                    "saturation": _round_int(_clamp(_scale(1, intensity), 0, 2)),
                }
            },
        )
    if move_name == "increase_color_presence":
        return {
            "vibrance": {
                "enabled": True,
                "pastels": _round_int(_clamp(_scale(8, intensity), 5, 12)),
                "saturated": _round_int(_clamp(_scale(4, intensity), 2, 7)),
                "protectskins": True,
                "avoidcolorshift": True,
            }
        }
    if move_name == "warm_memory":
        return {
            "white_balance": {
                "method": "Custom",
                "temperature": _round_int(_clamp(5500 + _scale(220, intensity), 5650, 5900)),
                "green": 1.0,
            },
            "vibrance": {
                "enabled": True,
                "pastels": _round_int(_clamp(_scale(6, intensity), 4, 9)),
                "saturated": _round_int(_clamp(_scale(2, intensity), 1, 4)),
                "protectskins": True,
                "avoidcolorshift": True,
            },
        }
    if move_name == "cool_melancholy":
        return {
            "white_balance": {
                "method": "Custom",
                "temperature": _round_int(_clamp(5500 - _scale(250, intensity), 5150, 5350)),
                "green": 1.01,
            },
            "exposure": {
                "saturation": _round_int(_clamp(_scale(-1, intensity), -2, 0)),
                "highlight_compression": _round_int(_clamp(_scale(16, intensity), 10, 24)),
            },
        }
    if move_name == "reduce_distractions":
        return {
            "exposure": {
                "saturation": _round_int(_clamp(_scale(-2, intensity), -3, -1)),
                "highlight_compression": _round_int(_clamp(_scale(12, intensity), 8, 18)),
            },
            "sharpening": {
                "enabled": True,
                "radius": 0.45,
                "amount": _round_int(_clamp(105 + 8 * scale, 105, 118)),
            },
        }
    if move_name == "enhance_geometry":
        return merge_parameter_sets(
            gentle_s_curve(),
            {
                "exposure": {
                    "contrast": _round_int(_clamp(_scale(5, intensity), 3, 7)),
                    "black": _round_int(_clamp(_scale(-2, intensity), -3, -1)),
                },
                "sharpening": {
                    "enabled": True,
                    "radius": 0.5,
                    "amount": _round_int(_clamp(125 + 10 * scale, 125, 140)),
                },
            },
        )
    if move_name == "protect_skin":
        return protect_skin_reduce_orange()
    if move_name == "natural_greens":
        return merge_parameter_sets(natural_green_control(), reduce_green_gray_cast())
    if move_name == "clean_sky":
        return merge_parameter_sets(clean_sky_blue(), soft_highlight_rolloff())
    if move_name == "lift_readability":
        return {
            "exposure": {
                "compensation": round(_clamp(_scale(0.16, intensity), 0.10, 0.24), 2),
                "contrast": _round_int(_clamp(_scale(3, intensity), 2, 5)),
                "highlight_compression": _round_int(_clamp(_scale(12, intensity), 8, 18)),
            },
            "luminance_curve": {
                "enabled": True,
                "contrast": _round_int(_clamp(_scale(5, intensity), 3, 7)),
                "avoid_color_shift": True,
                "red_skin_protection": 14 if portrait_like else 10,
            },
        }
    if move_name == "deepen_clean_shadows":
        return {
            "exposure": {
                "black": _round_int(_clamp(_scale(-3, intensity), -5, -2)),
                "contrast": _round_int(_clamp(_scale(2, intensity), 1, 4)),
            },
            "tone_curve": {
                "curve_mode": "Standard",
                "curve_mode2": "Standard",
                "curve2": "3;0;0;0.20;0.16;0.50;0.54;0.80;0.86;1;1;",
            },
        }
    if move_name == "soft_highlight_rolloff":
        return soft_highlight_rolloff()
    if move_name == "gentle_tonal_separation":
        return merge_parameter_sets(gentle_s_curve(), clean_midtone_contrast())
    if move_name == "calm_phone_filter_look":
        return {
            "exposure": {
                "saturation": _round_int(_clamp(_scale(-4, intensity), -5, -2)),
                "contrast": _round_int(_clamp(_scale(-1, intensity), -2, 0)),
            },
            "vibrance": {
                "enabled": True,
                "pastels": _round_int(_clamp(_scale(-1, intensity), -2, 0)),
                "saturated": _round_int(_clamp(_scale(-3, intensity), -4, -1)),
                "protectskins": True,
                "avoidcolorshift": True,
            },
        }
    if move_name == "preserve_event_authenticity":
        return {
            "exposure": {
                "compensation": round(_clamp(_scale(0.10, intensity), 0.05, 0.16), 2),
                "contrast": _round_int(_clamp(_scale(2, intensity), 1, 4)),
                "saturation": 0,
                "highlight_compression": _round_int(_clamp(_scale(10, intensity), 8, 14)),
            },
            "sharpening": {
                "enabled": True,
                "radius": 0.45,
                "amount": _round_int(_clamp(112 + 8 * scale, 112, 122)),
            },
            "noise_reduction": {
                "enabled": True,
                "luminance": 10,
                "chrominance": 10,
            },
        }

    return {}


_VISUAL_MOVE_REGISTRY: dict[str, dict[str, str]] = {
    "emphasize_subject": {
        "purpose": "Pull the eye toward the main subject through readable tone and local importance.",
        "when_to_use": "Subject is emotionally central but competes with the frame or feels slightly buried.",
        "when_to_avoid": "Silhouette or atmosphere should stay stronger than explicit subject clarity.",
        "risk": "Can over-flatten mood if exposure lift is pushed too far.",
        "safe_pp3_strategy_summary": (
            "Small exposure lift plus restrained luminance contrast with color-shift protection."
        ),
    },
    "preserve_silhouette": {
        "purpose": "Keep intentional darkness and edge shape as part of the story.",
        "when_to_use": "Atmosphere, sunset, or backlight matters more than lifting every shadow.",
        "when_to_avoid": "Viewer must clearly read the face or product detail.",
        "risk": "Too much restraint can feel underexposed instead of intentional.",
        "safe_pp3_strategy_summary": "Protect highlights and shadow shape without global brightening.",
    },
    "shape_light_break": {
        "purpose": "Make emerging light feel like the emotional release in the image.",
        "when_to_use": "Cloud breaks, fog openings, or directional sunlight drive the scene.",
        "when_to_avoid": "Light is already harsh or technically clipped everywhere.",
        "risk": "Can look fake if highlights are opened too aggressively.",
        "safe_pp3_strategy_summary": (
            "Use highlight rolloff, gentle compression, and modest tonal shaping around the light."
        ),
    },
    "deepen_cloud_weight": {
        "purpose": "Preserve atmospheric mass and seriousness in sky-heavy images.",
        "when_to_use": "Clouds or overcast tension are part of the emotional anchor.",
        "when_to_avoid": "Bright, airy weather is the actual appeal.",
        "risk": "Too much depth can turn weather into muddy heaviness.",
        "safe_pp3_strategy_summary": "Slight black point deepening, restrained contrast, and highlight protection.",
    },
    "soften_mist": {
        "purpose": "Keep fog, haze, and softness graceful instead of crunchy.",
        "when_to_use": "Mist and distance softness support mood or depth.",
        "when_to_avoid": "The image needs crisp architectural or product detail.",
        "risk": "Too much softness reduces presence and structure.",
        "safe_pp3_strategy_summary": "Lower contrast slightly, soften tone curve, and keep sharpening gentle.",
    },
    "enhance_water_depth": {
        "purpose": "Give water more depth, presence, and tonal separation.",
        "when_to_use": "Ocean, bay, river, or wet shoreline is part of the story.",
        "when_to_avoid": "Water is incidental and should not become the hero.",
        "risk": "Can drift into synthetic blue if overused.",
        "safe_pp3_strategy_summary": "Use mild blue/value shaping and small contrast depth, not split-toning.",
    },
    "increase_color_presence": {
        "purpose": "Add life and dimensional color without becoming loud.",
        "when_to_use": "The scene feels slightly dull but should stay natural.",
        "when_to_avoid": "Muted, documentary, or melancholy color is part of the point.",
        "risk": "Overuse creates phone-filter energy quickly.",
        "safe_pp3_strategy_summary": "Restrained vibrance with skin protection and color-shift avoidance.",
    },
    "warm_memory": {
        "purpose": "Nudge the edit toward warmth, nostalgia, and human memory.",
        "when_to_use": "Family, sunset memory, or affectionate travel mood calls for subtle warmth.",
        "when_to_avoid": "Cool neutrality or storm mood is more honest.",
        "risk": "Warmth stacks into orange skin or yellow haze if pushed too far.",
        "safe_pp3_strategy_summary": "Small WB warm shift and mild protected vibrance only.",
    },
    "cool_melancholy": {
        "purpose": "Preserve distance, quietness, and reflective cool mood.",
        "when_to_use": "Rain, dusk, or introspective atmosphere should stay cool and calm.",
        "when_to_avoid": "Skin warmth or hopeful sunlight is the emotional payoff.",
        "risk": "Can make scenes lifeless if all warmth disappears.",
        "safe_pp3_strategy_summary": "Slight WB cooling and restrained saturation reduction.",
    },
    "reduce_distractions": {
        "purpose": "Keep secondary areas from competing with the anchor.",
        "when_to_use": "Bright clutter or noisy detail steals attention.",
        "when_to_avoid": "A dense documentary frame depends on every detail staying equally alive.",
        "risk": "Can make the image feel muted if overdone.",
        "safe_pp3_strategy_summary": "Minor saturation pullback, mild highlight control, and calmer sharpening.",
    },
    "enhance_geometry": {
        "purpose": "Support shape, structure, and graphic rhythm.",
        "when_to_use": "Buildings, roads, shorelines, or repeating forms matter visually.",
        "when_to_avoid": "Soft atmosphere should dominate over crisp structure.",
        "risk": "Too much structure creates brittle edges.",
        "safe_pp3_strategy_summary": "Use small contrast and sharpening increases, not aggressive local contrast.",
    },
    "protect_skin": {
        "purpose": "Keep skin believable while other color edits happen.",
        "when_to_use": "People are present and skin should stay trustworthy.",
        "when_to_avoid": "No skin is present and color control is needed elsewhere.",
        "risk": "Too much protection can flatten desired warmth.",
        "safe_pp3_strategy_summary": "Use safe vibrance flags and restrained HSV correction around orange tones.",
    },
    "natural_greens": {
        "purpose": "Keep foliage depth without neon or gray-green drift.",
        "when_to_use": "Grass, hills, trees, or rural ambience matters.",
        "when_to_avoid": "Greens are not a noticeable part of the frame.",
        "risk": "Over-correction can drain life from vegetation.",
        "safe_pp3_strategy_summary": "Combine mild HSV foliage shaping with a subtle green-cast correction.",
    },
    "clean_sky": {
        "purpose": "Keep the sky controlled, believable, and free of cyan clipping.",
        "when_to_use": "Sky occupies meaningful area and can easily look synthetic.",
        "when_to_avoid": "Sky is minimal or intentionally hazy and unresolved.",
        "risk": "Can feel processed if sky treatment becomes too visible.",
        "safe_pp3_strategy_summary": "Pair safe blue control with gentle highlight rolloff.",
    },
    "lift_readability": {
        "purpose": "Make the image easier to read without changing its identity.",
        "when_to_use": "The frame is slightly murky but should not become bright-clean daytime.",
        "when_to_avoid": "Strong darkness or silhouette is the point.",
        "risk": "Can erase mystery if treated like exposure rescue.",
        "safe_pp3_strategy_summary": "Use a modest exposure lift plus protected luminance contrast.",
    },
    "deepen_clean_shadows": {
        "purpose": "Restore depth and shape in the darker half of the image.",
        "when_to_use": "The edit needs more grounding after highlight or readability work.",
        "when_to_avoid": "Shadow detail is already scarce and important.",
        "risk": "Can crush supporting detail if overused.",
        "safe_pp3_strategy_summary": "Lower black point slightly and use a gentle toe curve.",
    },
    "soft_highlight_rolloff": {
        "purpose": "Make bright areas feel open and natural instead of clipped.",
        "when_to_use": "Clouds, windows, sky, or pale skin need graceful highlight handling.",
        "when_to_avoid": "Highlights are already flat and low-contrast.",
        "risk": "Too much rolloff can make the image dull.",
        "safe_pp3_strategy_summary": "Use RT highlight recovery and highlight compression conservatively.",
    },
    "gentle_tonal_separation": {
        "purpose": "Create a more finished tonal hierarchy without obvious stylization.",
        "when_to_use": "The frame needs believable depth and editorial polish.",
        "when_to_avoid": "The scene already has strong native contrast and could turn brittle.",
        "risk": "Too much separation can tip into fake HDR texture.",
        "safe_pp3_strategy_summary": "Use a gentle global S-curve and mild luminance contrast.",
    },
    "calm_phone_filter_look": {
        "purpose": "Undo the feeling of a loud preset and return to tasteful restraint.",
        "when_to_use": "Color or contrast feels trendy, crunchy, or socially filtered.",
        "when_to_avoid": "The desired result should be celebratory or vividly stylized.",
        "risk": "Can oversoften the image if stacked repeatedly.",
        "safe_pp3_strategy_summary": "Pull back saturation and vibrance while preserving skin neutrality.",
    },
    "preserve_event_authenticity": {
        "purpose": "Polish the file while keeping the event feeling honest and lived-in.",
        "when_to_use": "Documentary, party, ceremony, or candid moments matter more than stylization.",
        "when_to_avoid": "Aesthetic mood-building is the clear goal over faithful memory.",
        "risk": "Too much correction can sterilize the event atmosphere.",
        "safe_pp3_strategy_summary": "Favor readability, modest cleanup, and neutral color discipline.",
    },
}


def build_editing_vision_contract(
    file_path: str,
    *,
    user_intent: str | None = None,
    context_hint: str | None = None,
) -> dict[str, Any]:
    """Return a structured editing-vision contract for LLM visual reasoning."""
    return {
        "file_path": file_path,
        "user_intent": user_intent,
        "context_hint": context_hint,
        "required_visual_questions": [
            "What do I love in this image right now?",
            "What is the emotional anchor or visual anchor?",
            "What should the viewer notice first?",
            "Which secondary elements support the story?",
            "What should become less important or quieter?",
            "What mood must be preserved even if technically imperfect?",
            "What would ruin this image if I edited too hard?",
            "What kind of edit would feel generic or fake here?",
            "Which safe visual moves best serve this image?",
        ],
        "editing_vision_schema": {
            "emotional_goal": "Short phrase describing what the final image should feel like.",
            "visual_anchor": "Primary subject/light/place element carrying the image.",
            "viewer_notice_first": "What the eye should land on first.",
            "supporting_elements": ["Secondary elements that support the story."],
            "deemphasize": ["Elements that should compete less."],
            "preserve": ["Mood, texture, color relationships, or atmosphere that must stay."],
            "avoid": ["What would feel fake, overprocessed, or against the scene."],
            "danger_notes": ["What would ruin the photo if pushed too far."],
            "editing_moves": list(_MOVE_NAMES),
            "notes": "Optional short explanation of why these moves fit the image.",
        },
        "visual_anchor_options": list(_VISUAL_ANCHOR_OPTIONS),
        "emotional_goal_options": list(_EMOTIONAL_GOAL_OPTIONS),
        "hierarchy_questions": [
            "What should become more important?",
            "What should become less important?",
            "Should the image read as subject-first, light-first, place-first, or atmosphere-first?",
        ],
        "preservation_questions": [
            "Which atmosphere, color relationship, or darkness level must survive the edit?",
            "What imperfections are actually part of the image's character?",
        ],
        "de_emphasis_questions": [
            "What currently competes with the anchor?",
            "What should be quieter rather than brighter or sharper?",
        ],
        "danger_questions": [
            "What would make this look like a preset instead of an edit?",
            "What would flatten the mood or erase authenticity?",
            "What should not be corrected away?",
        ],
        "suggested_visual_moves": list_visual_editing_moves()["moves"],
        "output_contract": {
            "precondition": "Preview the image first in this session before filling the editing vision.",
            "required_fields": [
                "emotional_goal",
                "visual_anchor",
                "viewer_notice_first",
                "supporting_elements",
                "deemphasize",
                "preserve",
                "avoid",
                "editing_moves",
            ],
            "response_format": "Return JSON-like structured values for downstream tools.",
            "example": {
                "emotional_goal": "mysterious rural cloud mood with hopeful light",
                "visual_anchor": "sunlit green fields under heavy cloud mass",
                "viewer_notice_first": "the light break across the fields",
                "supporting_elements": ["misty hills", "village", "waterline"],
                "deemphasize": ["flat foreground", "overly bright sky"],
                "preserve": ["fog", "cloud weight", "soft natural light"],
                "avoid": ["fake orange/blue grade", "crunchy clarity", "over-bright daylight look"],
                "editing_moves": [
                    "shape_light_break",
                    "deepen_cloud_weight",
                    "soften_mist",
                    "gentle_tonal_separation",
                ],
            },
        },
        "next_recommended_tools": [
            "list_visual_editing_moves",
            "create_editorial_brief",
            "generate_vision_candidates",
            "critique_gate",
        ],
    }


def list_visual_editing_moves() -> dict[str, Any]:
    """Return a compact palette of safe, high-level editorial moves."""
    moves = [{"name": move_name, **details} for move_name, details in _VISUAL_MOVE_REGISTRY.items()]
    return {
        "moves": moves,
        "philosophy": (
            "These are artistic editing moves, not a RawTherapee feature encyclopedia. "
            "Choose the moves that serve the image's purpose."
        ),
        "safety_notes": list(_SAFE_MOVE_NOTES),
    }


def _filtered_moves(moves: list[str]) -> list[str]:
    """Keep only supported move names while preserving order."""
    seen: set[str] = set()
    filtered: list[str] = []
    for move in moves:
        if move in _MOVE_NAMES and move not in seen:
            filtered.append(move)
            seen.add(move)
    return filtered


def _infer_moves_from_vision(editing_vision: dict[str, Any] | None) -> list[str]:
    """Infer a conservative fallback move stack from editing-vision text."""
    if not editing_vision:
        return list(_DEFAULT_VISION_MOVES)

    combined_text = " ".join(
        [
            str(editing_vision.get("emotional_goal", "")),
            str(editing_vision.get("visual_anchor", "")),
            " ".join(_string_list(editing_vision.get("preserve"))),
            " ".join(_string_list(editing_vision.get("avoid"))),
        ]
    ).lower()

    moves: list[str] = []
    if any(token in combined_text for token in ("fog", "mist", "haze")):
        moves.append("soften_mist")
    if any(token in combined_text for token in ("cloud", "storm", "overcast")):
        moves.append("deepen_cloud_weight")
    if any(token in combined_text for token in ("sun", "light break", "lightbreak", "hope", "glow")):
        moves.append("shape_light_break")
    if any(token in combined_text for token in ("ocean", "water", "bay", "shore")):
        moves.append("enhance_water_depth")
    if any(token in combined_text for token in ("field", "grass", "rural", "green")):
        moves.append("natural_greens")
    if any(token in combined_text for token in ("portrait", "face", "skin")):
        moves.append("protect_skin")
    if any(token in combined_text for token in ("event", "wedding", "party", "documentary")):
        moves.append("preserve_event_authenticity")
    if any(token in combined_text for token in ("geometry", "building", "architecture")):
        moves.append("enhance_geometry")
    if any(token in combined_text for token in ("warm", "memory", "sunset")):
        moves.append("warm_memory")
    if any(token in combined_text for token in ("cool", "melancholy", "rain", "quiet")):
        moves.append("cool_melancholy")

    moves.extend(_DEFAULT_VISION_MOVES)
    return _filtered_moves(moves)


def resolve_visual_moves(
    editing_vision: dict[str, Any] | None,
    *,
    include_support_moves: bool = True,
) -> list[str]:
    """Resolve visual moves from an editing-vision payload."""
    explicit_moves = _filtered_moves(_string_list((editing_vision or {}).get("editing_moves")))
    resolved = explicit_moves if explicit_moves else _infer_moves_from_vision(editing_vision)
    if include_support_moves:
        for move_name in _DEFAULT_VISION_MOVES:
            if move_name not in resolved:
                resolved.append(move_name)
    return resolved


def visual_moves_to_parameters(
    moves: list[str],
    intensity: str = "medium",
    intent_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert high-level visual moves into safe PP3 parameter groups."""
    normalized_intensity = _normalize_intensity(intensity)
    layers = [
        _move_parameters(move_name, normalized_intensity, intent_profile)
        for move_name in _filtered_moves(moves)
    ]
    merged = _merge_move_layers(layers)

    if "microcontrast" in merged:
        microcontrast = dict(merged["microcontrast"])
        microcontrast.pop("uniformity", None)
        microcontrast.pop("matrix", None)
        merged["microcontrast"] = microcontrast

    merged.pop("color_balance", None)
    merged.pop("split_toning", None)
    return merged


def _stronger_intensity(intensity: str) -> str:
    """Return a slightly stronger intensity label."""
    normalized = _normalize_intensity(intensity)
    if normalized == "low":
        return "medium"
    return "high"


def _lighter_intensity(intensity: str) -> str:
    """Return a slightly softer intensity label."""
    normalized = _normalize_intensity(intensity)
    if normalized == "high":
        return "medium"
    return "low"


def _pick_support_move(
    base_moves: list[str],
    candidate_pool: tuple[str, ...],
    avoid_text: str,
) -> str | None:
    """Choose one support move that is not already present."""
    for move_name in candidate_pool:
        if move_name not in base_moves and move_name not in avoid_text:
            return move_name
    return None


def build_vision_candidate_specs(
    editing_vision: dict[str, Any],
    *,
    intensity: str = "medium",
) -> list[dict[str, Any]]:
    """Build exactly three safe vision-first candidate plans."""
    resolved_moves = resolve_visual_moves(editing_vision)
    avoid_text = " ".join(_string_list(editing_vision.get("avoid"))).lower()
    preserve_values = _string_list(editing_vision.get("preserve"))
    emotional_goal = str(editing_vision.get("emotional_goal", "faithful vision-first refinement")).strip()
    visual_anchor = str(editing_vision.get("visual_anchor", "the image's main anchor")).strip()

    faithful_moves = resolved_moves[: min(4, len(resolved_moves))]
    faithful_support = _pick_support_move(faithful_moves, _FAITHFUL_SUPPORT_MOVES, avoid_text)
    if faithful_support:
        faithful_moves.append(faithful_support)

    expressive_moves = list(resolved_moves)
    expressive_support = _pick_support_move(expressive_moves, _EXPRESSIVE_SUPPORT_MOVES, avoid_text)
    if expressive_support:
        expressive_moves.append(expressive_support)

    experiment_moves = list(resolved_moves)
    experiment_support = _pick_support_move(experiment_moves, _EXPERIMENT_SUPPORT_MOVES, avoid_text)
    if experiment_support:
        experiment_moves.append(experiment_support)
    if "calm_phone_filter_look" in avoid_text and "calm_phone_filter_look" not in experiment_moves:
        experiment_moves.append("calm_phone_filter_look")

    return [
        {
            "candidate_name": "faithful_refinement",
            "parameter_intensity": _lighter_intensity(intensity),
            "visual_moves_used": _filtered_moves(faithful_moves),
            "intended_visual_effect": (
                f"Subtle, believable refinement that clarifies {visual_anchor} "
                "while staying close to the original mood."
            ),
            "what_it_preserves": preserve_values or ["original color relationships", "scene authenticity"],
            "risks_to_check_in_preview": [
                "May remain too subtle if the anchor still feels buried.",
                "Could under-communicate the emotional goal at thumbnail size.",
            ],
            "suggested_next_tools": ["preview_raw", "critique_gate", "adjust_profile"],
        },
        {
            "candidate_name": "expressive_refinement",
            "parameter_intensity": _normalize_intensity(intensity),
            "visual_moves_used": _filtered_moves(expressive_moves),
            "intended_visual_effect": (
                f"Clearer mood shaping for {emotional_goal} while still staying natural and editorial."
            ),
            "what_it_preserves": preserve_values or ["scene atmosphere", "natural color"],
            "risks_to_check_in_preview": [
                "Watch for the edit starting to feel like a preset instead of serving the vision.",
                "Check that supporting elements do not overpower the visual anchor.",
            ],
            "suggested_next_tools": ["preview_raw", "critique_gate", "adjust_profile"],
        },
        {
            "candidate_name": "restrained_experiment",
            "parameter_intensity": _stronger_intensity(intensity),
            "visual_moves_used": _filtered_moves(experiment_moves),
            "intended_visual_effect": (
                "A stronger interpretation that still respects atmosphere, safety limits, and authenticity."
            ),
            "what_it_preserves": preserve_values or ["core scene value"],
            "risks_to_check_in_preview": [
                "Strongest risk of flattening mood or over-shaping color hierarchy.",
                "Confirm the experiment still looks like the same photograph.",
            ],
            "suggested_next_tools": ["preview_raw", "critique_gate", "adjust_profile"],
        },
    ]
