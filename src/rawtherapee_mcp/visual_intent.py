"""Vision-first editing helpers built around safe high-level visual moves."""

from __future__ import annotations

from typing import Any

from rawtherapee_mcp.editing_techniques import combine_techniques, technique_risk_tags

ParameterSet = dict[str, dict[str, Any]]

_VALID_INTENSITIES = ("low", "medium", "high")
_INTENSITY_SCALE = {"low": 0.7, "medium": 1.0, "high": 1.25}
_MOVE_NAMES = (
    "emphasize_subject",
    "improve_composition",
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
_UNFILLED_CONTRACT_KEYS = (
    "editing_vision_schema",
    "required_visual_questions",
    "output_contract",
    "suggested_visual_moves",
)
_UNFILLED_CONTRACT_ERROR = (
    "This looks like an unfilled editing vision contract. Preview the image, fill emotional_goal, "
    "visual_anchor, preserve, avoid, and editing_moves, then call auto_edit_manifest_select_prepare."
)
_COLOR_DRIFT_AVOID_TERMS = (
    "orange/blue",
    "orange blue",
    "yellow/blue",
    "yellow blue",
    "cyan",
    "fake grade",
    "split",
    "synthetic blue",
    "postcard",
    "phone filter",
)
_WATER_ANCHOR_TERMS = ("water", "ocean", "bay", "sea")
_BLOCKED_COLOR_DRIFT_TAGS = {
    "cyan_shift",
    "blue_split",
    "synthetic_blue",
    "orange_shift",
    "warm_shift",
    "generic_pop",
}
_STREET_TRAVEL_GEOMETRY_TERMS = (
    "street",
    "travel",
    "tram",
    "rail",
    "rails",
    "wire",
    "wires",
    "architecture",
    "architectural",
    "building",
    "buildings",
    "urban",
    "city",
    "geometry",
    "composition",
    "postcard",
)
_SUPPORTED_ASPECT_RATIOS = ("original", "4:5", "3:2", "1:1", "16:9")


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


def _editing_vision_avoid_text(editing_vision: dict[str, Any] | None) -> str:
    """Return normalized avoid + danger text for alignment checks."""
    if not editing_vision:
        return ""
    avoid = " ".join(_string_list(editing_vision.get("avoid")))
    danger = " ".join(_string_list(editing_vision.get("danger_notes")))
    return f"{avoid} {danger}".strip().lower()


def _is_water_anchor(editing_vision: dict[str, Any] | None) -> bool:
    """Return True when the visual anchor is explicitly water-centric."""
    if not editing_vision:
        return False
    visual_anchor = str(editing_vision.get("visual_anchor", "")).lower()
    return any(term in visual_anchor for term in _WATER_ANCHOR_TERMS)


def _blocked_risk_tags(editing_vision: dict[str, Any] | None) -> set[str]:
    """Return risk tags that should be blocked from avoid/danger guidance."""
    avoid_text = _editing_vision_avoid_text(editing_vision)
    if any(term in avoid_text for term in _COLOR_DRIFT_AVOID_TERMS):
        return set(_BLOCKED_COLOR_DRIFT_TAGS)
    return set()


def _vision_combined_text(editing_vision: dict[str, Any] | None) -> str:
    """Return a normalized combined text blob for vision inference."""
    if not editing_vision:
        return ""
    return " ".join(
        [
            str(editing_vision.get("emotional_goal", "")),
            str(editing_vision.get("visual_anchor", "")),
            str(editing_vision.get("viewer_notice_first", "")),
            " ".join(_string_list(editing_vision.get("supporting_elements"))),
            " ".join(_string_list(editing_vision.get("preserve"))),
            " ".join(_string_list(editing_vision.get("avoid"))),
            " ".join(_string_list(editing_vision.get("danger_notes"))),
            " ".join(_string_list(editing_vision.get("editing_moves"))),
            str(editing_vision.get("notes", "")),
        ]
    ).lower()


def _is_street_travel_geometry_vision(editing_vision: dict[str, Any] | None) -> bool:
    """Return True when the vision is urban/travel/geometry-led."""
    combined_text = _vision_combined_text(editing_vision)
    return any(term in combined_text for term in _STREET_TRAVEL_GEOMETRY_TERMS)


_MOVE_TO_TECHNIQUES: dict[str, list[str]] = {
    "emphasize_subject": ["subject_readability_without_hdr", "gentle_tonal_separation"],
    "improve_composition": [],
    "preserve_silhouette": ["preserve_silhouette_tone", "soft_highlight_rolloff"],
    "shape_light_break": ["soft_highlight_rolloff", "shape_light_break_tonality", "subtle_shadow_depth"],
    "deepen_cloud_weight": ["gentle_tonal_separation", "subtle_shadow_depth", "soft_highlight_rolloff"],
    "soften_mist": ["muted_fog_contrast", "soft_highlight_rolloff", "calm_global_saturation"],
    "enhance_water_depth": ["subtle_water_luma_depth", "controlled_blue_presence", "gentle_tonal_separation"],
    "increase_color_presence": ["gentle_s_curve", "clean_midtone_contrast"],
    "warm_memory": ["skin_safe_warmth", "soft_highlight_rolloff"],
    "cool_melancholy": ["muted_fog_contrast", "calm_global_saturation"],
    "reduce_distractions": ["calm_global_saturation", "soft_highlight_rolloff"],
    "enhance_geometry": ["clean_midtone_contrast", "gentle_structure_without_crunch"],
    "protect_skin": ["skin_safe_warmth", "clean_neutral_balance"],
    "natural_greens": ["natural_green_compression", "reduce_green_gray_cast_safe"],
    "clean_sky": ["controlled_blue_presence", "soft_highlight_rolloff"],
    "lift_readability": ["subject_readability_without_hdr", "clean_midtone_contrast"],
    "deepen_clean_shadows": ["subtle_shadow_depth", "gentle_tonal_separation"],
    "soft_highlight_rolloff": ["soft_highlight_rolloff"],
    "gentle_tonal_separation": ["gentle_tonal_separation"],
    "calm_phone_filter_look": ["calm_global_saturation", "clean_neutral_balance"],
    "preserve_event_authenticity": ["clean_neutral_balance", "gentle_tonal_separation", "preserve_material_texture"],
}


def _move_risk_tags(move_name: str) -> set[str]:
    """Return aggregate risk tags for all techniques in one move."""
    tags: set[str] = set()
    for technique_name in _MOVE_TO_TECHNIQUES.get(move_name, []):
        tags.update(technique_risk_tags(technique_name))
    return tags


def _move_conflicts_with_vision(
    move_name: str,
    *,
    editing_vision: dict[str, Any] | None,
    blocked_tags: set[str],
    explicit_moves: set[str],
) -> bool:
    """Return True when a move conflicts with explicit avoid/danger guidance."""
    if move_name == "enhance_water_depth":
        # Water in supporting elements is not enough; the anchor must be water-centric.
        if not _is_water_anchor(editing_vision):
            return True
    if move_name in {"enhance_water_depth", "clean_sky"} and blocked_tags:
        # Only allow explicit requests when water is truly the anchor.
        if move_name in explicit_moves and _is_water_anchor(editing_vision):
            return False

    move_risk_tags = _move_risk_tags(move_name)
    structural_exception = move_name in {"enhance_geometry", "emphasize_subject"}
    effective_blocked_tags = blocked_tags - {"generic_pop"} if structural_exception else blocked_tags
    return bool(move_risk_tags & effective_blocked_tags)


def _filter_moves_by_vision(
    moves: list[str],
    *,
    editing_vision: dict[str, Any] | None,
    explicit_moves: set[str],
) -> list[str]:
    """Drop moves that violate avoid/danger guidance or water-anchor rules."""
    blocked_tags = _blocked_risk_tags(editing_vision)
    filtered: list[str] = []
    for move_name in _filtered_moves(moves):
        if _move_conflicts_with_vision(
            move_name,
            editing_vision=editing_vision,
            blocked_tags=blocked_tags,
            explicit_moves=explicit_moves,
        ):
            continue
        filtered.append(move_name)
    return filtered


def _anchor_priority_moves(editing_vision: dict[str, Any] | None) -> set[str]:
    """Return support moves aligned to the current visual anchor text."""
    if not editing_vision:
        return set()
    visual_anchor = str(editing_vision.get("visual_anchor", "")).lower()
    priorities: set[str] = set()
    if any(token in visual_anchor for token in ("sun", "light break", "lightbreak", "glow")):
        priorities.update({"shape_light_break", "soft_highlight_rolloff"})
    if any(token in visual_anchor for token in ("cloud", "storm", "overcast")):
        priorities.add("deepen_cloud_weight")
    if any(token in visual_anchor for token in ("fog", "mist", "haze")):
        priorities.add("soften_mist")
    if any(token in visual_anchor for token in ("field", "grass", "rural", "green")):
        priorities.add("natural_greens")
    if any(token in visual_anchor for token in _WATER_ANCHOR_TERMS):
        priorities.add("enhance_water_depth")
    return priorities


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
    "improve_composition": {
        "purpose": "Use crop and framing review to strengthen hierarchy before escalating global styling.",
        "when_to_use": "Subject, geometry, or place context is present but thumbnail impact and hierarchy feel weak.",
        "when_to_avoid": "The full-frame context is the point and tighter framing would remove the story.",
        "risk": "Can damage balance through over-cropping or a forced aspect ratio.",
        "safe_pp3_strategy_summary": (
            "Plan 2-3 crop variants, preview them, and keep geometry/anchor "
            "edges intentional."
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
            "Can crop or framing improve hierarchy more than global tone/color?",
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
            "create_composition_plan",
            "create_editorial_brief",
            "get_compact_manifest_summary",
            "auto_edit_manifest_select_prepare",
            "verify_predictive_edit",
            "generate_crop_candidates",
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


def _normalize_aspect_ratio(aspect_ratio: str | None) -> str:
    """Return a supported aspect ratio label for composition planning."""
    normalized = (aspect_ratio or "original").strip().lower()
    return normalized if normalized in _SUPPORTED_ASPECT_RATIOS else "original"


def build_crop_candidate_specs(
    editing_vision: dict[str, Any] | None,
    *,
    aspect_ratio: str = "original",
) -> list[dict[str, str]]:
    """Return conservative crop-variant planning descriptors.

    This is composition planning only. It does not inspect pixels.
    """
    requested_ratio = _normalize_aspect_ratio(aspect_ratio)
    geometry_led = _is_street_travel_geometry_vision(editing_vision)
    combined_text = _vision_combined_text(editing_vision)

    candidates = [
        {
            "candidate_name": "original_aspect_tighten",
            "aspect_ratio": "original",
            "intent": "Tighten weak empty space while preserving the photograph's native feel.",
            "crop_strategy": "Reduce dead foreground and edge drift first while keeping the original aspect.",
            "likely_benefit": "Improves hierarchy without introducing a more stylized framing change.",
            "risk": "May still feel too polite if the original aspect ratio is part of the hierarchy problem.",
        },
        {
            "candidate_name": "4x5_travel_vertical",
            "aspect_ratio": "4:5",
            "intent": "Make the subject/place hierarchy read faster in a travel-friendly vertical frame.",
            "crop_strategy": "Trim weak foreground first and keep the anchor large enough to pop at thumbnail size.",
            "likely_benefit": "Often improves mobile/postcard readability for street and travel frames.",
            "risk": "Can cut too much breathing room or sky if pushed mechanically.",
        },
        {
            "candidate_name": "3x2_clean_geometry",
            "aspect_ratio": "3:2",
            "intent": "Preserve line flow and structural rhythm in a classic geometry-friendly frame.",
            "crop_strategy": "Keep line entry and exit points clean so rails, roads, or facades still guide the eye.",
            "likely_benefit": "Can balance subject scale and urban geometry better than a tighter vertical crop.",
            "risk": "If the source already lives near this family, the visible change may be small.",
        },
    ]

    if geometry_led and "wire" in combined_text:
        candidates[2]["crop_strategy"] = (
            "Keep rail and wire entry points clean; avoid trimming the strongest intersections at the frame edges."
        )

    if requested_ratio != "original":
        candidates.sort(key=lambda item: (item["aspect_ratio"] != requested_ratio, item["candidate_name"]))

    return candidates


def build_composition_plan(
    file_path: str,
    editing_vision: dict[str, Any] | None,
    *,
    aspect_ratio: str = "original",
) -> dict[str, Any]:
    """Return a crop/framing planning contract from editing-vision language.

    This helper intentionally does not perform computer vision. It translates
    the editing vision into a stricter composition review so the LLM previews
    crop variants before concluding that global edits are not enough.
    """
    normalized_ratio = _normalize_aspect_ratio(aspect_ratio)
    combined_text = _vision_combined_text(editing_vision)
    geometry_led = _is_street_travel_geometry_vision(editing_vision)
    visual_anchor = str((editing_vision or {}).get("visual_anchor", "")).strip()
    viewer_notice_first = str((editing_vision or {}).get("viewer_notice_first", "")).strip()
    deemphasize = _string_list((editing_vision or {}).get("deemphasize"))

    leading_lines: list[str] = []
    preserve_edges: list[str] = []
    distractions_to_crop = list(deemphasize)

    if any(term in combined_text for term in ("tram", "rail", "rails")):
        leading_lines.append("rail corridor and track convergence")
        preserve_edges.append("Keep the tram nose and at least one clean rail entry readable.")
    if any(term in combined_text for term in ("wire", "wires", "catenary", "pole", "poles")):
        leading_lines.append("overhead wire geometry and repeating support poles")
        preserve_edges.append("Avoid trimming the strongest wire intersections at the top edge.")
    if any(term in combined_text for term in ("street", "road", "urban", "city", "architecture", "geometry")):
        leading_lines.append("street depth and repeating urban structure")
        preserve_edges.append("Protect the cleanest structural corridor at the frame edge.")

    if geometry_led and not distractions_to_crop:
        distractions_to_crop = [
            "dead foreground or empty lower frame that delays the subject read",
            "edge clutter that competes before the anchor and leading lines take over",
            "non-essential sky if it weakens the graphic corridor",
        ]

    if not leading_lines:
        leading_lines.append("the strongest directional shapes that point toward the visual anchor")
    if not preserve_edges:
        preserve_edges.append("Preserve the clearest anchor edge and strongest route into the frame.")

    rotate_or_straighten_suggestion = (
        "Check whether vertical supports or horizon-adjacent structures lean; only apply a slight straighten if it "
        "makes the geometry feel more intentional without harming edge balance."
    )
    if not geometry_led:
        rotate_or_straighten_suggestion = (
            "Straighten only if a visible lean distracts from the anchor; "
            "avoid rotation that creates awkward edge loss."
        )

    return {
        "file_path": file_path,
        "editing_vision": editing_vision,
        "requested_aspect_ratio": normalized_ratio,
        "composition_anchor": visual_anchor or "the primary subject/place anchor",
        "leading_lines": leading_lines,
        "distractions_to_crop": distractions_to_crop,
        "preserve_edges": preserve_edges,
        "crop_candidates": build_crop_candidate_specs(editing_vision, aspect_ratio=normalized_ratio),
        "rotate_or_straighten_suggestion": rotate_or_straighten_suggestion,
        "thumbnail_goal": (
            viewer_notice_first
            or visual_anchor
            or "Make the main anchor read clearly before secondary context."
        ),
        "risk_notes": [
            "Do not crop away the reason the image exists just to force impact.",
            "Avoid clipping the strongest line entry/exit points at the edges.",
            "Treat crop as a preview decision first; do not export from crop alone.",
        ],
        "required_visual_questions": [
            "Can crop or framing improve hierarchy more than global tone/color?",
            "Which edges must stay intact so the anchor still feels intentional?",
            "What dead space can be reduced without making the frame feel cramped?",
            "Would a 4:5 or 3:2 variant improve thumbnail impact more than subtle global styling?",
        ],
        "next_recommended_tools": ["generate_crop_candidates", "preview_raw", "critique_gate"],
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

    combined_text = _vision_combined_text(editing_vision)
    visual_anchor = str(editing_vision.get("visual_anchor", ""))
    visual_anchor_text = visual_anchor.lower()

    moves: list[str] = []
    if any(token in combined_text for token in ("fog", "mist", "haze")):
        moves.append("soften_mist")
    if any(token in combined_text for token in ("cloud", "storm", "overcast")):
        moves.append("deepen_cloud_weight")
    if any(token in combined_text for token in ("sun", "light break", "lightbreak", "hope", "glow")):
        moves.append("shape_light_break")
    if any(token in visual_anchor_text for token in _WATER_ANCHOR_TERMS):
        moves.append("enhance_water_depth")
    if any(token in combined_text for token in ("field", "grass", "rural", "green")):
        moves.append("natural_greens")
    if any(token in combined_text for token in ("portrait", "face", "skin")):
        moves.append("protect_skin")
    if any(token in combined_text for token in ("event", "wedding", "party", "documentary")):
        moves.append("preserve_event_authenticity")
    if any(token in combined_text for token in ("geometry", "building", "architecture")):
        moves.append("enhance_geometry")
        moves.append("improve_composition")
    if any(token in combined_text for token in ("tram", "street", "urban", "city", "architecture", "geometry")):
        moves.append("emphasize_subject")
    if any(token in combined_text for token in ("travel", "street", "urban", "city", "tram", "postcard")):
        moves.append("enhance_geometry")
        moves.append("improve_composition")
        moves.append("reduce_distractions")
    if any(
        token in combined_text
        for token in ("warm", "summer", "mediterranean", "postcard", "travel", "city energy")
    ):
        moves.append("warm_memory")
    if any(token in combined_text for token in ("travel", "postcard", "summer", "city energy")):
        moves.append("increase_color_presence")
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
    return _filter_moves_by_vision(
        resolved,
        editing_vision=editing_vision,
        explicit_moves=set(explicit_moves),
    )


def visual_moves_to_parameter_plan(
    moves: list[str],
    intensity: str = "medium",
    intent_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a full debug plan for visual-move to parameter composition."""
    _normalize_intensity(intensity)
    moves_requested = list(moves)
    explicit_moves = _filtered_moves(_string_list((intent_profile or {}).get("editing_moves")))
    blocked_tags = _blocked_risk_tags(intent_profile)
    filtered_requested_moves = _filtered_moves(moves_requested)

    visual_moves_used: list[str] = []
    visual_moves_blocked: list[str] = []
    techniques_requested: list[str] = []
    techniques_blocked: list[str] = []
    technique_names: list[str] = []

    for move_name in filtered_requested_moves:
        move_techniques = _MOVE_TO_TECHNIQUES.get(move_name, [])
        techniques_requested.extend(move_techniques)

        if _move_conflicts_with_vision(
            move_name,
            editing_vision=intent_profile,
            blocked_tags=blocked_tags,
            explicit_moves=set(explicit_moves),
        ):
            visual_moves_blocked.append(move_name)
            techniques_blocked.extend(move_techniques)
            continue

        visual_moves_used.append(move_name)
        allow_blocked_tags = (
            move_name in {"enhance_water_depth", "clean_sky"}
            and move_name in explicit_moves
            and _is_water_anchor(intent_profile)
        )
        for technique_name in move_techniques:
            effective_blocked_tags = blocked_tags
            if move_name in {"enhance_geometry", "emphasize_subject"}:
                effective_blocked_tags = blocked_tags - {"generic_pop"}
            if (
                effective_blocked_tags
                and (set(technique_risk_tags(technique_name)) & effective_blocked_tags)
                and not allow_blocked_tags
            ):
                techniques_blocked.append(technique_name)
                continue
            technique_names.append(technique_name)

    merged = combine_techniques(technique_names)
    return {
        "moves_requested": moves_requested,
        "visual_moves_used": visual_moves_used,
        "visual_moves_blocked": visual_moves_blocked,
        "techniques_used": merged["techniques_used"],
        "techniques_blocked": techniques_blocked,
        "unknown_techniques": merged["unknown_techniques"],
        "overwritten_parameters": merged["overwritten_parameters"],
        "blocked_risk_tags": sorted(blocked_tags),
        "parameters": merged["parameters"],
    }


def visual_moves_to_parameters(
    moves: list[str],
    intensity: str = "medium",
    intent_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert high-level visual moves into safe technique-composed parameters."""
    plan = visual_moves_to_parameter_plan(
        moves,
        intensity=intensity,
        intent_profile=intent_profile,
    )
    parameters = plan["parameters"]
    return parameters if isinstance(parameters, dict) else {}


def validate_filled_editing_vision(editing_vision: dict[str, Any]) -> str | None:
    """Return error text when editing_vision looks like an unfilled contract."""
    if any(key in editing_vision for key in _UNFILLED_CONTRACT_KEYS):
        return _UNFILLED_CONTRACT_ERROR

    emotional_goal = str(editing_vision.get("emotional_goal", "")).strip()
    visual_anchor = str(editing_vision.get("visual_anchor", "")).strip()
    editing_moves = _string_list(editing_vision.get("editing_moves"))
    if not emotional_goal or not visual_anchor or not editing_moves:
        return _UNFILLED_CONTRACT_ERROR
    return None


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
    editing_vision: dict[str, Any],
) -> str | None:
    """Choose one support move that is not already present."""
    explicit_moves = set(_filtered_moves(_string_list(editing_vision.get("editing_moves"))))
    blocked_tags = _blocked_risk_tags(editing_vision)
    preferred = _anchor_priority_moves(editing_vision)

    for move_name in candidate_pool:
        if move_name in base_moves:
            continue
        if move_name not in preferred:
            continue
        if _move_conflicts_with_vision(
            move_name,
            editing_vision=editing_vision,
            blocked_tags=blocked_tags,
            explicit_moves=explicit_moves,
        ):
            continue
        return move_name

    for move_name in candidate_pool:
        if move_name in base_moves:
            continue
        if _move_conflicts_with_vision(
            move_name,
            editing_vision=editing_vision,
            blocked_tags=blocked_tags,
            explicit_moves=explicit_moves,
        ):
            continue
        return move_name
    return None


def _add_assertive_support_moves(
    base_moves: list[str],
    candidate_pool: tuple[str, ...],
    editing_vision: dict[str, Any],
    *,
    limit: int,
) -> list[str]:
    """Append up to ``limit`` extra support moves without violating vision rules."""
    updated_moves = list(base_moves)
    while limit > 0:
        support_move = _pick_support_move(updated_moves, candidate_pool, editing_vision)
        if support_move is None:
            break
        updated_moves.append(support_move)
        limit -= 1
    return updated_moves


def build_vision_candidate_specs(
    editing_vision: dict[str, Any],
    *,
    intensity: str = "medium",
) -> list[dict[str, Any]]:
    """Build exactly three safe vision-first candidate plans."""
    validation_error = validate_filled_editing_vision(editing_vision)
    if validation_error:
        raise ValueError(validation_error)

    resolved_moves = resolve_visual_moves(editing_vision)
    preserve_values = _string_list(editing_vision.get("preserve"))
    emotional_goal = str(editing_vision.get("emotional_goal", "faithful vision-first refinement")).strip()
    visual_anchor = str(editing_vision.get("visual_anchor", "the image's main anchor")).strip()
    street_travel_geometry_vision = _is_street_travel_geometry_vision(editing_vision)
    geometry_or_crop_suggested = street_travel_geometry_vision or "enhance_geometry" in resolved_moves

    faithful_moves = resolved_moves[: min(4, len(resolved_moves))]
    faithful_support = _pick_support_move(faithful_moves, _FAITHFUL_SUPPORT_MOVES, editing_vision)
    if faithful_support:
        faithful_moves.append(faithful_support)

    expressive_moves = list(resolved_moves)
    expressive_support = _pick_support_move(expressive_moves, _EXPRESSIVE_SUPPORT_MOVES, editing_vision)
    if expressive_support:
        expressive_moves.append(expressive_support)
    if street_travel_geometry_vision:
        expressive_moves = _add_assertive_support_moves(
            expressive_moves,
            ("emphasize_subject", "enhance_geometry", "increase_color_presence", "warm_memory", "lift_readability"),
            editing_vision,
            limit=2,
        )

    experiment_moves = list(resolved_moves)
    experiment_support = _pick_support_move(experiment_moves, _EXPERIMENT_SUPPORT_MOVES, editing_vision)
    if experiment_support:
        experiment_moves.append(experiment_support)
    if street_travel_geometry_vision:
        experiment_moves = _add_assertive_support_moves(
            experiment_moves,
            ("emphasize_subject", "enhance_geometry", "increase_color_presence", "warm_memory", "lift_readability"),
            editing_vision,
            limit=3,
        )
    avoid_text = _editing_vision_avoid_text(editing_vision)
    if "phone filter" in avoid_text and "calm_phone_filter_look" not in experiment_moves:
        experiment_moves.append("calm_phone_filter_look")

    expressive_intensity = (
        _stronger_intensity(intensity) if street_travel_geometry_vision else _normalize_intensity(intensity)
    )
    experiment_intensity = _stronger_intensity(intensity)

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
            "visible_difference_score": "0-10 after preview",
            "visual_hierarchy_improvement_score": "0-10 after preview",
            "thumbnail_impact_score": "0-10 after preview",
            "composition_improvement_needed": "yes|no after preview",
            "crop_or_geometry_suggested": geometry_or_crop_suggested,
            "suggested_next_tools": (
                [
                    "create_composition_plan",
                    "generate_crop_candidates",
                    "preview_raw",
                    "verify_predictive_edit",
                ]
                if geometry_or_crop_suggested
                else ["preview_raw", "verify_predictive_edit"]
            ),
        },
        {
            "candidate_name": "expressive_refinement",
            "parameter_intensity": expressive_intensity,
            "visual_moves_used": _filtered_moves(expressive_moves),
            "intended_visual_effect": (
                f"Clearer mood shaping for {emotional_goal} while still staying natural and editorial."
            ),
            "what_it_preserves": preserve_values or ["scene atmosphere", "natural color"],
            "risks_to_check_in_preview": [
                "Watch for the edit starting to feel like a preset instead of serving the vision.",
                "Check that supporting elements do not overpower the visual anchor.",
            ],
            "visible_difference_score": "0-10 after preview",
            "visual_hierarchy_improvement_score": "0-10 after preview",
            "thumbnail_impact_score": "0-10 after preview",
            "composition_improvement_needed": "yes|no after preview",
            "crop_or_geometry_suggested": geometry_or_crop_suggested,
            "suggested_next_tools": (
                [
                    "create_composition_plan",
                    "generate_crop_candidates",
                    "preview_raw",
                    "verify_predictive_edit",
                ]
                if geometry_or_crop_suggested
                else ["preview_raw", "verify_predictive_edit"]
            ),
        },
        {
            "candidate_name": "restrained_experiment",
            "parameter_intensity": experiment_intensity,
            "visual_moves_used": _filtered_moves(experiment_moves),
            "intended_visual_effect": (
                "A stronger interpretation that still respects atmosphere, safety limits, and authenticity."
            ),
            "what_it_preserves": preserve_values or ["core scene value"],
            "risks_to_check_in_preview": [
                "Strongest risk of flattening mood or over-shaping color hierarchy.",
                "Confirm the experiment still looks like the same photograph.",
            ],
            "visible_difference_score": "0-10 after preview",
            "visual_hierarchy_improvement_score": "0-10 after preview",
            "thumbnail_impact_score": "0-10 after preview",
            "composition_improvement_needed": "yes|no after preview",
            "crop_or_geometry_suggested": geometry_or_crop_suggested,
            "suggested_next_tools": (
                [
                    "create_composition_plan",
                    "generate_crop_candidates",
                    "preview_raw",
                    "verify_predictive_edit",
                ]
                if geometry_or_crop_suggested
                else ["preview_raw", "verify_predictive_edit"]
            ),
        },
    ]
