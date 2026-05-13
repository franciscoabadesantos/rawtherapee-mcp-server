"""Tests for vision-first editing helpers."""

from __future__ import annotations

import pytest

from rawtherapee_mcp.visual_intent import (
    build_editing_vision_contract,
    build_vision_candidate_specs,
    list_visual_editing_moves,
    resolve_visual_moves,
    visual_moves_to_parameter_plan,
    visual_moves_to_parameters,
)


class TestBuildEditingVisionContract:
    """Tests for editing-vision contract builder."""

    def test_returns_expected_schema(self):
        contract = build_editing_vision_contract(
            "photo.cr3",
            user_intent="hopeful fog",
            context_hint="rural coast",
        )
        expected_keys = {
            "file_path",
            "user_intent",
            "context_hint",
            "required_visual_questions",
            "editing_vision_schema",
            "visual_anchor_options",
            "emotional_goal_options",
            "hierarchy_questions",
            "preservation_questions",
            "de_emphasis_questions",
            "danger_questions",
            "suggested_visual_moves",
            "output_contract",
            "next_recommended_tools",
        }
        assert expected_keys.issubset(set(contract.keys()))
        assert "emotional_goal" in contract["editing_vision_schema"]
        assert "generate_vision_candidates" in contract["next_recommended_tools"]


class TestVisualEditingMoves:
    """Tests for compact move palette and safe move translation."""

    def test_lists_compact_move_palette(self):
        moves = list_visual_editing_moves()
        move_names = {move["name"] for move in moves["moves"]}

        assert "shape_light_break" in move_names
        assert "enhance_water_depth" in move_names
        assert "preserve_event_authenticity" in move_names
        assert "safety_notes" in moves

    def test_visual_moves_to_parameters_avoids_known_unsafe_settings(self):
        parameters = visual_moves_to_parameters(
            [
                "shape_light_break",
                "soften_mist",
                "increase_color_presence",
                "natural_greens",
            ],
            intensity="high",
        )

        assert "color_balance" not in parameters
        assert "split_toning" not in parameters
        assert "microcontrast" not in parameters or "uniformity" not in parameters["microcontrast"]

    def test_resolve_visual_moves_uses_explicit_moves_before_inference(self):
        moves = resolve_visual_moves(
            {
                "editing_moves": ["shape_light_break", "soften_mist"],
                "emotional_goal": "warm hopeful light",
            }
        )

        assert moves[:2] == ["shape_light_break", "soften_mist"]
        assert "gentle_tonal_separation" in moves

    def test_avoid_yellow_blue_split_blocks_controlled_blue_presence_by_default(self):
        plan = visual_moves_to_parameter_plan(
            ["clean_sky"],
            intent_profile={
                "visual_anchor": "sunlight over rural fields",
                "avoid": ["yellow/blue split", "fake grade"],
            },
        )
        params = plan["parameters"]
        hsv = params.get("hsv_equalizer", {})
        assert "clean_sky" in plan["visual_moves_blocked"]
        assert "controlled_blue_presence" in plan["techniques_blocked"]
        assert "cyan_shift" in plan["blocked_risk_tags"]
        assert "v_curve" not in hsv

    def test_avoid_yellow_blue_split_allows_controlled_blue_only_for_explicit_water_anchor(self):
        plan = visual_moves_to_parameter_plan(
            ["enhance_water_depth"],
            intent_profile={
                "visual_anchor": "ocean water mass and bay horizon",
                "editing_moves": ["enhance_water_depth"],
                "avoid": ["yellow/blue split", "fake grade"],
            },
        )
        params = plan["parameters"]
        hsv = params.get("hsv_equalizer", {})
        assert "enhance_water_depth" in plan["visual_moves_used"]
        assert "controlled_blue_presence" in plan["techniques_used"]
        assert hsv.get("enabled") is True
        assert "v_curve" in hsv

    def test_parameter_plan_includes_technique_debug_fields(self):
        plan = visual_moves_to_parameter_plan(
            ["shape_light_break", "soften_mist", "gentle_tonal_separation"],
            intensity="medium",
        )
        assert plan["moves_requested"] == ["shape_light_break", "soften_mist", "gentle_tonal_separation"]
        assert plan["visual_moves_used"]
        assert plan["techniques_used"]
        assert isinstance(plan["overwritten_parameters"], list)
        assert isinstance(plan["unknown_techniques"], list)
        assert "parameters" in plan

    def test_supporting_water_alone_does_not_trigger_water_enhancement(self):
        moves = resolve_visual_moves(
            {
                "emotional_goal": "mysterious rural cloud mood with hopeful light",
                "visual_anchor": "sunlight breaking through over the fields under heavy clouds",
                "supporting_elements": ["waterline"],
                "preserve": ["mist", "cloud weight"],
                "avoid": ["fake orange/blue grade"],
            }
        )
        assert "enhance_water_depth" not in moves


class TestVisionCandidateSpecs:
    """Tests for three-candidate vision planning."""

    def test_rejects_unfilled_contract(self):
        contract = build_editing_vision_contract("photo.cr3")
        with pytest.raises(ValueError, match="unfilled editing vision contract"):
            build_vision_candidate_specs(contract, intensity="medium")

    def test_builds_exactly_three_candidates(self):
        editing_vision = {
            "emotional_goal": "mysterious rural cloud mood with hopeful light",
            "visual_anchor": "sunlit fields under cloud mass",
            "preserve": ["fog", "cloud weight"],
            "avoid": ["fake preset look"],
            "editing_moves": ["shape_light_break", "deepen_cloud_weight", "soften_mist"],
        }

        specs = build_vision_candidate_specs(editing_vision, intensity="medium")

        assert len(specs) == 3
        assert [spec["candidate_name"] for spec in specs] == [
            "faithful_refinement",
            "expressive_refinement",
            "restrained_experiment",
        ]
        for spec in specs:
            assert spec["visual_moves_used"]
            assert "suggested_next_tools" in spec

    def test_rural_cloud_anchor_stays_out_of_blue_split_direction(self):
        editing_vision = {
            "emotional_goal": "mysterious rural cloud mood with hopeful light",
            "visual_anchor": "sunlight breaking through over the fields under heavy clouds",
            "supporting_elements": ["village", "waterline"],
            "preserve": ["fog", "cloud weight", "soft natural light"],
            "avoid": ["fake orange/blue grade", "yellow/blue split", "generic postcard brightness"],
            "danger_notes": ["no synthetic blue", "no phone filter look"],
            "editing_moves": [
                "shape_light_break",
                "deepen_cloud_weight",
                "soften_mist",
                "gentle_tonal_separation",
                "natural_greens",
            ],
        }

        specs = build_vision_candidate_specs(editing_vision, intensity="medium")
        assert [spec["candidate_name"] for spec in specs] == [
            "faithful_refinement",
            "expressive_refinement",
            "restrained_experiment",
        ]
        for spec in specs:
            assert "enhance_water_depth" not in spec["visual_moves_used"]
            assert "increase_color_presence" not in spec["visual_moves_used"]
            assert "warm_memory" not in spec["visual_moves_used"]
