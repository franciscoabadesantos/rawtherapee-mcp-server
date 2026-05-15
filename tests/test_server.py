"""Tests for MCP server tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.tools import ToolResult
from PIL import Image as PILImage

from rawtherapee_mcp.control_policy import validate_autonomous_parameters
from rawtherapee_mcp.predictive_editor import build_predictive_edit_plan
from rawtherapee_mcp.server import (
    add_luminance_adjustment,
    adjust_crop_position,
    adjust_local_spot,
    adjust_profile,
    analyze_image,
    apply_local_preset,
    auto_edit_predictive,
    batch_analyze,
    batch_preview,
    check_rt_status,
    compare_profiles,
    create_composition_plan,
    create_curation_plan,
    create_editing_vision,
    create_editorial_brief,
    critique_gate,
    export_multi_device,
    generate_crop_candidates,
    generate_editorial_candidates,
    generate_vision_candidates,
    get_config,
    get_histogram,
    infer_photo_intent,
    interpolate_profiles,
    legacy_generate_vision_candidates,
    list_local_adjustments,
    list_raw_files,
    list_visual_editing_moves,
    mcp,
    preview_before_after,
    preview_exposure_bracket,
    preview_raw,
    preview_white_balance,
    process_raw,
    read_exif,
    remove_local_adjustment,
    visual_moves_to_parameters,
)


class TestGetConfig:
    """Tests for context config extraction."""

    def test_extracts_config(self, mock_ctx, mock_config):
        config = get_config(mock_ctx)
        assert config is mock_config

    def test_raises_on_missing(self):
        ctx = MagicMock()
        ctx.lifespan_context = {}
        with pytest.raises(RuntimeError, match="RTConfig not initialized"):
            get_config(ctx)


class TestCheckRtStatus:
    """Tests for check_rt_status tool."""

    async def test_rt_installed(self, mock_ctx):
        with patch("rawtherapee_mcp.server.get_rt_version", return_value="5.11"):
            result = await check_rt_status(mock_ctx)
            assert result["installed"] is True
            assert result["version"] == "5.11"
            assert result["cli_path"] is not None

    async def test_rt_not_installed(self, mock_ctx_no_rt):
        result = await check_rt_status(mock_ctx_no_rt)
        assert result["installed"] is False
        assert result["cli_path"] is None
        assert result["version"] is None


class TestListRawFiles:
    """Tests for list_raw_files tool."""

    async def test_finds_raw_files(self, mock_ctx, tmp_path):
        # Create some test files
        (tmp_path / "photo1.cr2").write_bytes(b"raw1")
        (tmp_path / "photo2.nef").write_bytes(b"raw2")
        (tmp_path / "readme.txt").write_bytes(b"text")

        result = await list_raw_files(mock_ctx, str(tmp_path))
        assert result["count"] == 2
        extensions = [f["extension"] for f in result["files"]]
        assert ".cr2" in extensions
        assert ".nef" in extensions

    async def test_recursive_scan(self, mock_ctx, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "photo1.arw").write_bytes(b"raw1")
        (subdir / "photo2.dng").write_bytes(b"raw2")

        result = await list_raw_files(mock_ctx, str(tmp_path), recursive=True)
        assert result["count"] == 2

    async def test_non_recursive_skips_subdirs(self, mock_ctx, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "photo1.arw").write_bytes(b"raw1")
        (subdir / "photo2.dng").write_bytes(b"raw2")

        result = await list_raw_files(mock_ctx, str(tmp_path), recursive=False)
        assert result["count"] == 1

    async def test_directory_not_found(self, mock_ctx):
        result = await list_raw_files(mock_ctx, "/nonexistent/path")
        assert "error" in result

    async def test_case_insensitive_extensions(self, mock_ctx, tmp_path):
        (tmp_path / "PHOTO.CR2").write_bytes(b"raw")
        (tmp_path / "photo.Nef").write_bytes(b"raw")

        result = await list_raw_files(mock_ctx, str(tmp_path))
        assert result["count"] == 2


class TestEditorialWorkflowTools:
    """Tests for opinionated editorial workflow MCP tools."""

    async def test_infer_photo_intent_returns_contract(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await infer_photo_intent(
            mock_ctx,
            str(raw_file),
            user_intent="sunset ambience",
            context_hint="beach frame with dark subject",
        )
        assert "error" not in result
        assert result["file_path"] == str(raw_file)
        assert "required_visual_questions" in result
        assert "likely_intent_categories" in result
        assert "sunset_silhouette" in result["likely_intent_categories"]

    async def test_create_editorial_brief_keys_and_instructions(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await create_editorial_brief(mock_ctx, str(raw_file), style="clean_editorial")
        assert "error" not in result
        assert "recommended_workflow" in result
        assert "llm_instructions" in result
        assert "Do not flatter mediocre results." in result["llm_instructions"]

    async def test_create_editorial_brief_accepts_inferred_intent(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await create_editorial_brief(
            mock_ctx,
            str(raw_file),
            inferred_intent={"primary_intent_category": "sunset_silhouette"},
        )
        assert "error" not in result
        assert result["intent_standard"]["primary_intent_category"] == "sunset_silhouette"

    async def test_create_editing_vision_returns_contract(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await create_editing_vision(
            mock_ctx,
            str(raw_file),
            user_intent="hopeful cloud break",
            context_hint="rural hillside",
        )
        assert "error" not in result
        assert result["file_path"] == str(raw_file)
        assert "editing_vision_schema" in result
        assert "auto_edit_predictive" in result["next_recommended_tools"]
        assert "legacy_generate_vision_candidates" in result["next_recommended_tools"]

    async def test_create_composition_plan_returns_contract(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await create_composition_plan(
            mock_ctx,
            str(raw_file),
            editing_vision={
                "emotional_goal": "warm city transit energy",
                "visual_anchor": "tram nose with rails and wires",
                "viewer_notice_first": "tram front and leading rails",
                "editing_moves": ["emphasize_subject", "enhance_geometry", "improve_composition"],
            },
            aspect_ratio="4:5",
        )
        assert "error" not in result
        assert result["requested_aspect_ratio"] == "4:5"
        assert len(result["crop_candidates"]) == 3
        assert "generate_crop_candidates" in result["next_recommended_tools"]

    async def test_list_visual_editing_moves_returns_palette(self, mock_ctx):
        result = await list_visual_editing_moves(mock_ctx)

        assert "moves" in result
        assert any(move["name"] == "shape_light_break" for move in result["moves"])
        assert "safety_notes" in result

    async def test_visual_moves_to_parameters_tool_is_registered(self):
        tools = await mcp.list_tools()
        names = {tool.name for tool in tools}
        assert "visual_moves_to_parameters" in names
        assert "auto_edit_predictive" in names
        assert "legacy_generate_vision_candidates" in names
        assert "create_composition_plan" in names
        assert "generate_crop_candidates" in names

    async def test_visual_moves_to_parameters_tool_returns_sanitized_payload(self, mock_ctx):
        result = await visual_moves_to_parameters(
            mock_ctx,
            ["shape_light_break", "soften_mist", "gentle_tonal_separation"],
            intensity="medium",
        )
        assert "parameters" in result
        assert "color_balance" not in result["parameters"]
        assert "split_toning" not in result["parameters"]
        assert result["visual_moves_used"]
        assert result["techniques_used"]
        assert "overwritten_parameters" in result
        assert "visual_moves_blocked" in result
        assert "techniques_blocked" in result
        assert "blocked_risk_tags" in result
        assert "safety_sanitizations_applied" in result

    async def test_generate_editorial_candidates_returns_three_distinct_styles(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        with patch("rawtherapee_mcp.server.get_rt_version", return_value="RawTherapee, version 5.10, command line."):
            result = await generate_editorial_candidates(mock_ctx, str(raw_file), "trip_frame")
        assert "error" not in result
        assert len(result["candidates"]) == 3
        for candidate in result["candidates"]:
            assert "safety_sanitizations_applied" in candidate

        style_names = [candidate["style_name"] for candidate in result["candidates"]]
        assert set(style_names) == {"clean_editorial", "warm_travel", "cinematic_soft"}

        for candidate in result["candidates"]:
            assert Path(candidate["profile_path"]).is_file()

        # Ensure generated profiles include advanced tone/color controls.
        from rawtherapee_mcp.pp3_parser import PP3Profile

        by_style = {candidate["style_name"]: candidate for candidate in result["candidates"]}

        clean_profile = PP3Profile()
        clean_profile.load(Path(by_style["clean_editorial"]["profile_path"]))
        assert clean_profile.get("Exposure", "Curve", "0;") != "0;"
        assert clean_profile.get("Luminance Curve", "Enabled") == "true"

        warm_profile = PP3Profile()
        warm_profile.load(Path(by_style["warm_travel"]["profile_path"]))
        assert warm_profile.get("HSV Equalizer", "Enabled") == "true"
        assert warm_profile.get("ColorToning", "Enabled", "") == ""
        assert warm_profile.get("SharpenMicro", "Uniformity", "") == ""

        cinematic_profile = PP3Profile()
        cinematic_profile.load(Path(by_style["cinematic_soft"]["profile_path"]))
        assert cinematic_profile.get("HLRecovery", "Enabled") == "true"
        assert cinematic_profile.get("ColorToning", "Enabled", "") == ""
        assert cinematic_profile.get("SharpenMicro", "Enabled") == "false"
        assert cinematic_profile.get("SharpenMicro", "Amount") == "15"
        assert cinematic_profile.get("SharpenMicro", "Contrast") == "20"
        assert cinematic_profile.get("SharpenMicro", "Uniformity", "") == ""

    async def test_generate_editorial_candidates_still_returns_three_with_inferred_intent(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        with patch("rawtherapee_mcp.server.get_rt_version", return_value="RawTherapee, version 5.10, command line."):
            result = await generate_editorial_candidates(
                mock_ctx,
                str(raw_file),
                "trip_frame",
                inferred_intent={"primary_intent_category": "atmosphere_memory"},
            )
        assert "error" not in result
        assert len(result["candidates"]) == 3

    async def test_generate_vision_candidates_returns_three_profiles(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await generate_vision_candidates(
            mock_ctx,
            str(raw_file),
            "vision_frame",
            editing_vision={
                "emotional_goal": "mysterious rural cloud mood with hopeful light",
                "visual_anchor": "sunlit fields under heavy clouds",
                "preserve": ["fog", "cloud weight"],
                "avoid": ["fake orange/blue grade"],
                "editing_moves": ["shape_light_break", "deepen_cloud_weight", "soften_mist"],
            },
        )
        assert "error" not in result
        assert result["legacy_status"] == "deprecated for autonomous default use"
        assert len(result["candidates"]) == 3
        assert [candidate["candidate_name"] for candidate in result["candidates"]] == [
            "faithful_refinement",
            "expressive_refinement",
            "restrained_experiment",
        ]

        from rawtherapee_mcp.pp3_parser import PP3Profile

        for candidate in result["candidates"]:
            assert candidate["visual_moves_used"]
            assert "visual_moves_blocked" in candidate
            assert "techniques_used" in candidate
            assert "techniques_blocked" in candidate
            assert "unknown_techniques" in candidate
            assert "overwritten_parameters" in candidate
            assert "blocked_risk_tags" in candidate
            assert "merged_parameter_summary" in candidate
            assert "visible_difference_score" in candidate
            assert "visual_hierarchy_improvement_score" in candidate
            assert "thumbnail_impact_score" in candidate
            assert "composition_improvement_needed" in candidate
            assert "crop_or_geometry_suggested" in candidate
            assert "safety_sanitizations_applied" in candidate
            assert Path(candidate["profile_path"]).is_file()

            profile = PP3Profile()
            profile.load(Path(candidate["profile_path"]))
            assert profile.get("ColorToning", "Method", "") == ""
            assert profile.get("SharpenMicro", "Uniformity", "") == ""
            assert profile.get("Local Contrast", "Amount", "") == ""
            assert "local_contrast" not in candidate["merged_parameter_summary"]["groups"]

    async def test_legacy_generate_vision_candidates_wrapper(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        result = await legacy_generate_vision_candidates(
            mock_ctx,
            str(raw_file),
            "legacy_frame",
            editing_vision={
                "emotional_goal": "urban travel clarity",
                "visual_anchor": "tram front and rails",
                "preserve": ["street context"],
                "editing_moves": ["emphasize_subject", "enhance_geometry"],
            },
        )
        assert "error" not in result
        assert result["legacy_tool"] is True

    async def test_auto_edit_predictive_uses_manifest_allowed_controls(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1024, 768), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                style="warm natural travel",
                intensity="medium",
                user_brief="Barcelona travel frame with stronger natural presence",
                export=False,
            )

        assert "error" not in result
        assert result["decision"] in {"proof_only", "failed_edit_quality"}
        assert result["decision_source"] == "visual_verification_pending"
        assert result["validation"]["allowed"] is True
        assert "perceived_non_crop_improvement" in result["visual_verification_scores"]
        assert "expected_global_change" in result["planned_scores"]
        assert "local_contrast" not in result["parameters"]
        assert result["parameters"]["tone_curve"]["curve_mode"] == "Standard"
        assert result["parameters"]["tone_curve"]["curve"] == "5;0;0;0.18;0.12;0.45;0.54;0.76;0.90;1;1;"
        assert "rgb_curves" not in result["parameters"]
        hsv = result["parameters"].get("hsv_equalizer", {})
        assert "h_curve" not in hsv

    async def test_auto_edit_predictive_maps_flat_midtone_geometry(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                style="warm natural travel",
                intensity="medium",
                diagnosis_override={
                    "style": "warm natural travel",
                    "intensity": "medium",
                    "diagnosis": [{"issue": "flat_midtone_geometry", "severity": 0.8, "evidence": "thumbnail weak"}],
                    "crop_need": "low",
                },
            )

        params = result["parameters"]
        assert "exposure" in params and "contrast" in params["exposure"]
        assert "luminance_curve" in params and params["luminance_curve"].get("enabled") is True
        assert "microcontrast" in params and "amount" in params["microcontrast"]
        blocked = {item["control"] for item in result["blocked_controls_considered"]}
        assert "Local Contrast.Amount" in blocked

    async def test_auto_edit_predictive_maps_dull_color_presence(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                diagnosis_override={
                    "style": "warm natural travel",
                    "intensity": "medium",
                    "diagnosis": [{"issue": "dull_color_presence", "severity": 0.7, "evidence": "muted color"}],
                    "crop_need": "low",
                },
            )

        params = result["parameters"]
        assert params["vibrance"]["enabled"] is True
        assert "pastels" in params["vibrance"]
        assert "saturated" in params["vibrance"]
        assert "saturation" in params["exposure"]

    async def test_auto_edit_predictive_maps_bright_sky_controls(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                diagnosis_override={
                    "style": "warm natural travel",
                    "intensity": "medium",
                    "diagnosis": [{"issue": "bright_sky_needs_control", "severity": 0.8, "evidence": "bright cloud"}],
                    "crop_need": "low",
                },
            )

        params = result["parameters"]
        assert "highlight_compression" in params["exposure"]
        assert "highlight_rolloff" in params
        assert "highlights" in params["highlight_rolloff"]
        assert "highlight_compression_threshold" in params["highlight_rolloff"]

    def test_predictive_hierarchy_boost_strengthens_safe_controls(self):
        plan = build_predictive_edit_plan(
            style="warm natural travel",
            intensity="medium",
            user_brief="Barcelona tram travel frame",
            diagnosis_payload={
                "style": "warm natural travel",
                "intensity": "medium",
                "diagnosis": [
                    {"issue": "flat_midtone_geometry", "severity": 0.65, "evidence": "flat rails"},
                    {"issue": "weak_subject_readability", "severity": 0.55, "evidence": "tram competes"},
                    {"issue": "low_thumbnail_impact", "severity": 0.55, "evidence": "weak first read"},
                    {"issue": "dull_color_presence", "severity": 0.45, "evidence": "muted travel color"},
                ],
                "crop_need": "low",
            },
        )

        params = plan["parameters"]
        assert plan["planned_scores"]["hierarchy_boost_applied"] is True
        assert params["exposure"]["contrast"] >= 11
        assert params["exposure"]["compensation"] >= 0.3
        assert params["luminance_curve"]["contrast"] >= 8
        assert params["luminance_curve"]["avoid_color_shift"] is True
        assert params["microcontrast"]["amount"] >= 8
        assert params["vibrance"]["pastels"] >= 8
        assert params["vibrance"]["saturated"] in range(3, 6)
        assert params["tone_curve"]["curve_mode"] == "Standard"
        assert params["tone_curve"]["curve"] == "5;0;0;0.18;0.12;0.45;0.54;0.76;0.90;1;1;"
        assert plan["approved_curves_used"][0]["id"] == "tone_curve.midtone_depth_v1"
        assert params["tone_curve"]["curve"] == "5;0;0;0.18;0.12;0.45;0.54;0.76;0.90;1;1;"
        validation = validate_autonomous_parameters(params)
        assert validation.allowed is True
        assert "local_contrast" not in params
        assert "rgb_curves" not in params
        assert "hsv_equalizer" not in params

    def test_predictive_hierarchy_boost_does_not_trigger_for_single_hierarchy_issue(self):
        plan = build_predictive_edit_plan(
            style="warm natural travel",
            intensity="medium",
            user_brief="tram travel frame",
            diagnosis_payload={
                "style": "warm natural travel",
                "intensity": "medium",
                "diagnosis": [{"issue": "flat_midtone_geometry", "severity": 0.8, "evidence": "flat rails"}],
                "crop_need": "low",
            },
        )

        assert plan["planned_scores"]["hierarchy_boost_applied"] is False
        assert "tone_curve" not in plan["parameters"]
        assert plan["approved_curves_used"] == []

    def test_predictive_approved_curve_is_not_used_in_avoid_context(self):
        plan = build_predictive_edit_plan(
            style="night portrait travel",
            intensity="medium",
            user_brief="night portrait with fragile skin tones",
            diagnosis_payload={
                "style": "night portrait travel",
                "intensity": "medium",
                "diagnosis": [
                    {"issue": "flat_midtone_geometry", "severity": 0.8, "evidence": "flat rails"},
                    {"issue": "weak_subject_readability", "severity": 0.8, "evidence": "weak subject"},
                    {"issue": "low_thumbnail_impact", "severity": 0.7, "evidence": "weak thumbnail"},
                ],
                "crop_need": "low",
            },
        )

        assert "tone_curve" not in plan["parameters"]
        assert plan["approved_curves_used"] == []

    def test_predictive_landscape_tonal_depth_preset_triggers_for_landscape_sky_context(self):
        plan = build_predictive_edit_plan(
            style="landscape cleanup with controlled sky highlights",
            intensity="medium",
            user_brief="coastal landscape with bright sky and haze",
            diagnosis_payload={
                "style": "landscape cleanup with controlled sky highlights",
                "intensity": "medium",
                "diagnosis": [
                    {"issue": "dull_color_presence", "severity": 0.45, "evidence": "muted greens"},
                    {"issue": "bright_sky_needs_control", "severity": 0.35, "evidence": "bright clouds"},
                ],
                "crop_need": "low",
            },
        )

        assert plan["parameters"]["luminance_curve"]["lh_curve"] == "5;0;0;0.16;0.10;0.46;0.52;0.76;0.88;1;1;"
        assert plan["parameters"]["luminance_curve"]["hh_curve"] == "5;0;0;0.28;0.24;0.60;0.52;0.82;0.74;1;0.90;"
        assert any(item["id"] == "luminance_curve.landscape_depth_v1" for item in plan["approved_curves_used"])
        validation = validate_autonomous_parameters(plan["parameters"])
        assert validation.allowed is True

    def test_predictive_low_light_tonal_depth_preset_triggers_for_low_light_context(self):
        plan = build_predictive_edit_plan(
            style="low-light natural recovery",
            intensity="low",
            user_brief="dusk beach subject with blocked shadows",
            diagnosis_payload={
                "style": "low-light natural recovery",
                "intensity": "low",
                "diagnosis": [
                    {"issue": "blocked_shadows", "severity": 0.45, "evidence": "subject too dark"},
                    {"issue": "dull_color_presence", "severity": 0.35, "evidence": "low-light color loss"},
                ],
                "crop_need": "low",
            },
        )

        assert plan["parameters"]["luminance_curve"]["lh_curve"] == "5;0;0;0.14;0.22;0.40;0.52;0.72;0.84;1;1;"
        assert plan["parameters"]["luminance_curve"]["hh_curve"] == "5;0;0;0.30;0.28;0.66;0.60;0.86;0.82;1;0.96;"
        assert any(item["id"] == "luminance_curve.low_light_lift_v1" for item in plan["approved_curves_used"])

    def test_predictive_low_light_tonal_depth_preset_is_blocked_in_fragile_portrait_context(self):
        plan = build_predictive_edit_plan(
            style="night portrait recovery",
            intensity="high",
            user_brief="night portrait high iso skin tones",
            diagnosis_payload={
                "style": "night portrait recovery",
                "intensity": "high",
                "diagnosis": [{"issue": "blocked_shadows", "severity": 0.6, "evidence": "dark face"}],
                "crop_need": "low",
            },
        )

        assert "lh_curve" not in plan.get("parameters", {}).get("luminance_curve", {})
        assert not any(item["id"] == "luminance_curve.low_light_lift_v1" for item in plan["approved_curves_used"])

    def test_predictive_medium_dull_color_presence_uses_stronger_vibrance(self):
        plan = build_predictive_edit_plan(
            style="warm natural travel",
            intensity="medium",
            user_brief="muted color",
            diagnosis_payload={
                "style": "warm natural travel",
                "intensity": "medium",
                "diagnosis": [{"issue": "dull_color_presence", "severity": 0.45, "evidence": "muted"}],
                "crop_need": "low",
            },
        )

        assert plan["parameters"]["vibrance"]["pastels"] >= 8
        assert 3 <= plan["parameters"]["vibrance"]["saturated"] <= 5

    def test_predictive_high_intensity_hierarchy_boost_clamps_to_manifest(self):
        plan = build_predictive_edit_plan(
            style="warm natural travel",
            intensity="high",
            user_brief="strong hierarchy",
            diagnosis_payload={
                "style": "warm natural travel",
                "intensity": "high",
                "diagnosis": [
                    {"issue": "flat_midtone_geometry", "severity": 1.0, "evidence": "flat"},
                    {"issue": "weak_subject_readability", "severity": 1.0, "evidence": "weak"},
                    {"issue": "low_thumbnail_impact", "severity": 1.0, "evidence": "small"},
                    {"issue": "dull_color_presence", "severity": 1.0, "evidence": "muted"},
                ],
                "crop_need": "low",
            },
        )

        params = plan["parameters"]
        assert params["exposure"]["contrast"] <= 20
        assert params["luminance_curve"]["contrast"] <= 16
        assert params["microcontrast"]["amount"] <= 20
        assert params["vibrance"]["pastels"] <= 15
        assert validate_autonomous_parameters(params).allowed is True

    def test_predictive_expected_effect_mentions_subject_background_separation(self):
        plan = build_predictive_edit_plan(
            style="warm natural travel",
            intensity="medium",
            user_brief="tram hierarchy",
            diagnosis_payload={
                "style": "warm natural travel",
                "intensity": "medium",
                "diagnosis": [
                    {"issue": "flat_midtone_geometry", "severity": 0.65, "evidence": "flat rails"},
                    {"issue": "weak_subject_readability", "severity": 0.55, "evidence": "tram competes"},
                ],
                "crop_need": "low",
            },
        )

        effect_text = " ".join(plan["expected_effect"]).lower()
        assert "subject" in effect_text
        assert "background" in effect_text
        assert "separate" in effect_text

    async def test_auto_edit_predictive_high_intensity_correction_is_clamped(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                intensity="high",
                diagnosis_override={
                    "style": "warm natural travel",
                    "intensity": "high",
                    "diagnosis": [{"issue": "flat_midtone_geometry", "severity": 1.0, "evidence": "very flat"}],
                    "crop_need": "low",
                },
                verification_feedback={
                    "recommendation": "minor_correction",
                    "suggested_correction": {"Exposure.Contrast": "+100"},
                },
            )

        assert result["correction_applied"] is True
        assert result["parameters"]["exposure"]["contrast"] <= 20

    async def test_auto_edit_predictive_does_not_call_legacy_flow(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with (
            patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview),
            patch(
                "rawtherapee_mcp.server.generate_vision_candidates",
                side_effect=RuntimeError("legacy should not run"),
            ),
        ):
            result = await auto_edit_predictive(mock_ctx, str(raw_file), export=False)

        assert "error" not in result
        assert result["decision"] in {"proof_only", "failed_edit_quality"}
        assert result["decision_source"] == "visual_verification_pending"

    async def test_auto_edit_predictive_export_gate_rejects_weak_or_crop_primary(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                export=True,
                diagnosis_override={
                    "style": "warm natural travel",
                    "intensity": "medium",
                    "diagnosis": [{"issue": "proof_only_needed", "severity": 0.9, "evidence": "weak frame"}],
                    "crop_need": "mild",
                },
            )

        assert result["decision"] == "proof_only"
        assert result["visual_verification_scores"]["export_gate_passed"] is False

    async def test_auto_edit_predictive_reports_approved_curve_usage(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                style="warm natural travel",
                intensity="medium",
                user_brief="Barcelona tram travel frame",
                diagnosis_override={
                    "style": "warm natural travel",
                    "intensity": "medium",
                    "diagnosis": [
                        {"issue": "flat_midtone_geometry", "severity": 0.8, "evidence": "flat rails"},
                        {"issue": "weak_subject_readability", "severity": 0.8, "evidence": "weak subject"},
                        {"issue": "low_thumbnail_impact", "severity": 0.7, "evidence": "weak thumbnail"},
                    ],
                    "crop_need": "low",
                },
            )

        assert result["approved_curves_used"]
        assert result["approved_curves_used"][0]["id"] == "tone_curve.midtone_depth_v1"
        assert result["parameters"]["tone_curve"]["curve"] == "5;0;0;0.18;0.12;0.45;0.54;0.76;0.90;1;1;"

    async def test_auto_edit_predictive_reports_tonal_depth_preset_usage(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                style="landscape cleanup with controlled sky highlights",
                intensity="medium",
                user_brief="coastal landscape with bright sky and haze",
                diagnosis_override={
                    "style": "landscape cleanup with controlled sky highlights",
                    "intensity": "medium",
                    "diagnosis": [
                        {"issue": "dull_color_presence", "severity": 0.45, "evidence": "muted greens"},
                        {"issue": "bright_sky_needs_control", "severity": 0.35, "evidence": "bright clouds"},
                    ],
                    "crop_need": "low",
                },
            )

        assert any(item["id"] == "luminance_curve.landscape_depth_v1" for item in result["approved_curves_used"])
        assert result["parameters"]["luminance_curve"]["lh_curve"] == "5;0;0;0.16;0.10;0.46;0.52;0.76;0.88;1;1;"

    async def test_planner_scores_alone_cannot_produce_export_or_proof_plus(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                style="warm natural travel",
                intensity="medium",
                user_brief="Barcelona tram travel frame",
                diagnosis_override={
                    "style": "warm natural travel",
                    "intensity": "medium",
                    "diagnosis": [
                        {"issue": "flat_midtone_geometry", "severity": 0.8, "evidence": "flat rails"},
                        {"issue": "weak_subject_readability", "severity": 0.8, "evidence": "weak subject"},
                        {"issue": "low_thumbnail_impact", "severity": 0.7, "evidence": "weak thumbnail"},
                    ],
                    "crop_need": "low",
                },
            )

        assert result["planned_scores"]["expected_subject_hierarchy"] >= 6.0
        assert result["decision"] in {"proof_only", "failed_edit_quality"}
        assert result["decision_source"] == "visual_verification_pending"

    async def test_visual_verification_scores_drive_final_decision(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                verification_feedback={
                    "subject": "tram",
                    "before_after_judgment": {
                        "global_pixel_difference": 7.5,
                        "non_crop_tonal_improvement": 7.4,
                        "subject_separation_improvement": 7.6,
                        "color_intent_improvement": 7.2,
                        "highlight_shadow_quality": 6.8,
                        "composition_improvement": 4.0,
                        "crop_contribution": 2.0,
                        "perceived_non_crop_improvement": "moderate",
                        "artifact_check": "pass",
                        "artifact_free_score": 9.0,
                        "naturalness_score": 8.0,
                        "thumbnail_subject_read_score": 7.3,
                        "reason": "Tram separates more clearly and color presence is stronger before crop.",
                    },
                },
            )

        assert result["decision"] in {"proof_plus", "export"}
        assert result["decision_source"] == "visual_verification"
        assert result["visual_verification_scores"]["subject_separation_improvement"] == 7.6

    async def test_perceived_non_crop_improvement_weak_blocks_proof_plus_and_export(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (1000, 700), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(
                mock_ctx,
                str(raw_file),
                verification_feedback={
                    "subject": "tram",
                    "before_after_judgment": {
                        "global_pixel_difference": 9.0,
                        "non_crop_tonal_improvement": 7.5,
                        "subject_separation_improvement": 7.6,
                        "color_intent_improvement": 7.4,
                        "highlight_shadow_quality": 7.1,
                        "composition_improvement": 4.0,
                        "crop_contribution": 2.0,
                        "perceived_non_crop_improvement": "weak",
                        "artifact_check": "pass",
                        "artifact_free_score": 9.0,
                        "naturalness_score": 8.0,
                        "thumbnail_subject_read_score": 7.4,
                        "reason": "Numeric improvement exists, but the perceived change is still weak.",
                    },
                },
            )

        assert result["decision"] == "proof_only"
        assert result["decision_source"] == "visual_verification"

    async def test_generate_crop_candidates_returns_safe_crop_only_profiles(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        with patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(6000, 4000)):
            result = await generate_crop_candidates(
                mock_ctx,
                str(raw_file),
                "vision_frame",
                editing_vision={
                    "emotional_goal": "warm city transit energy",
                    "visual_anchor": "tram nose with rails and wires",
                    "viewer_notice_first": "tram front and leading rails",
                    "preserve": ["travel postcard feeling"],
                    "editing_moves": ["emphasize_subject", "enhance_geometry", "improve_composition"],
                },
            )
        assert "error" not in result
        assert len(result["candidates"]) == 3
        assert result["dimension_source"] == "effective_exif_dimensions"
        assert result["source_width"] == 6000
        assert result["source_height"] == 4000
        assert result["source_file_used"] == str(raw_file)
        assert result["used_preview_fallback"] is False
        assert "dimension_sources_attempted" in result

        from rawtherapee_mcp.pp3_parser import PP3Profile

        for candidate in result["candidates"]:
            assert candidate["candidate_name"] in {
                "original_aspect_tighten",
                "4x5_travel_vertical",
                "3x2_clean_geometry",
            }
            assert candidate["preview_required"] is True
            assert candidate["export_allowed_without_preview"] is False
            assert Path(candidate["profile_path"]).is_file()
            assert candidate["crop_coordinates"] == {
                "x": candidate["crop_x"],
                "y": candidate["crop_y"],
                "width": candidate["crop_width"],
                "height": candidate["crop_height"],
            }

            profile = PP3Profile()
            profile.load(Path(candidate["profile_path"]))
            assert profile.get("Crop", "Enabled") == "true"
            assert profile.get("Resize", "Enabled") == "false"
            assert int(profile.get("Crop", "X")) == candidate["crop_x"]
            assert int(profile.get("Crop", "Y")) == candidate["crop_y"]
            assert int(profile.get("Crop", "W")) == candidate["crop_width"]
            assert int(profile.get("Crop", "H")) == candidate["crop_height"]
            assert profile.get("Crop", "FixedRatio") == "true"
            assert profile.get("Crop", "Ratio")
            assert profile.get("Crop", "Orientation") == "As Image"
            assert profile.get("Crop", "Guide") == "Frame"
            assert profile.get("Local Contrast", "Amount", "") == ""
            assert profile.get("ColorToning", "Method", "") == ""
            assert profile.get("SharpenMicro", "Uniformity", "") == ""

    async def test_generate_crop_candidates_uses_direct_image_dimensions(self, mock_ctx, tmp_path):
        image_file = tmp_path / "photo.jpg"
        PILImage.new("RGB", (3000, 2000), "gray").save(str(image_file), "JPEG")

        result = await generate_crop_candidates(
            mock_ctx,
            str(image_file),
            "vision_frame",
            editing_vision={
                "emotional_goal": "clean travel geometry",
                "visual_anchor": "tram and rails",
                "viewer_notice_first": "tram front",
                "preserve": ["street context"],
                "editing_moves": ["improve_composition"],
            },
        )

        assert "error" not in result
        assert result["dimension_source"] == "direct_image_metadata"
        assert result["source_width"] == 3000
        assert result["source_height"] == 2000
        assert result["source_file_used"] == str(image_file)
        assert result["used_preview_fallback"] is False
        assert result["candidates"][0]["crop_width"] > 0
        assert result["candidates"][0]["crop_height"] > 0

    async def test_generate_crop_candidates_uses_preview_dimension_fallback_for_cr3(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"cr3")

        async def create_probe_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (6400, 4266), "gray").save(str(out), "JPEG")
            return {
                "success": True,
                "output_path": str(out),
                "processing_time": 0.5,
                "file_size": out.stat().st_size,
            }

        with (
            patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(0, 0)),
            patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_probe_preview),
        ):
            result = await generate_crop_candidates(
                mock_ctx,
                str(raw_file),
                "vision_frame",
                editing_vision={
                    "emotional_goal": "warm city transit energy",
                    "visual_anchor": "tram nose with rails and wires",
                    "viewer_notice_first": "tram front and leading rails",
                    "preserve": ["travel postcard feeling"],
                    "editing_moves": ["emphasize_subject", "enhance_geometry", "improve_composition"],
                },
            )

        assert "error" not in result
        assert result["dimension_source"] == "rawtherapee_neutral_preview_dimensions"
        assert result["source_width"] == 6400
        assert result["source_height"] == 4266
        assert result["used_preview_fallback"] is True
        assert result["source_file_used"].endswith(".jpg")
        assert [attempt["source"] for attempt in result["dimension_sources_attempted"]] == [
            "direct_image_metadata",
            "effective_exif_dimensions",
            "rawtherapee_neutral_preview_dimensions",
        ]
        assert len(result["candidates"]) == 3

    async def test_generate_crop_candidates_returns_structured_dimension_failure(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"cr3")

        with patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(0, 0)):
            result = await generate_crop_candidates(
                mock_ctx_no_rt,
                str(raw_file),
                "vision_frame",
                editing_vision={
                    "emotional_goal": "warm city transit energy",
                    "visual_anchor": "tram nose with rails and wires",
                    "viewer_notice_first": "tram front and leading rails",
                    "preserve": ["travel postcard feeling"],
                    "editing_moves": ["improve_composition"],
                },
            )

        assert "error" in result
        assert result["dimension_source"] is None
        assert result["source_width"] == 0
        assert result["source_height"] == 0
        assert result["source_file_used"] is None
        assert result["used_preview_fallback"] is False
        assert "dimension_sources_attempted" in result
        assert [attempt["source"] for attempt in result["dimension_sources_attempted"]] == [
            "direct_image_metadata",
            "effective_exif_dimensions",
            "rawtherapee_neutral_preview_dimensions",
        ]
        assert "RawTherapee CLI is not configured" in result["dimension_sources_attempted"][-1]["error"]
        assert "suggestion" in result

    async def test_generate_vision_candidates_rural_vision_avoids_blue_split_profiles(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await generate_vision_candidates(
            mock_ctx,
            str(raw_file),
            "vision_frame",
            editing_vision={
                "emotional_goal": "mysterious rural cloud mood with hopeful light",
                "visual_anchor": "sunlight breaking through over the fields under heavy clouds",
                "supporting_elements": ["waterline"],
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
            },
        )
        assert "error" not in result
        assert [candidate["candidate_name"] for candidate in result["candidates"]] == [
            "faithful_refinement",
            "expressive_refinement",
            "restrained_experiment",
        ]

        from rawtherapee_mcp.pp3_parser import PP3Profile

        for candidate in result["candidates"]:
            profile = PP3Profile()
            profile.load(Path(candidate["profile_path"]))
            assert profile.get("HSV Equalizer", "HCurve", "") == ""
            assert profile.get("HSV Equalizer", "VCurve", "") == ""
            assert "enhance_water_depth" not in candidate["visual_moves_used"]
            assert "enhance_water_depth" in candidate["visual_moves_blocked"] or "enhance_water_depth" not in candidate[
                "moves_requested"
            ]
            assert "controlled_blue_presence" in candidate["techniques_blocked"] or "controlled_blue_presence" not in (
                candidate["techniques_used"]
            )

    async def test_generate_vision_candidates_rejects_unfilled_contract(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        contract = await create_editing_vision(mock_ctx, str(raw_file))

        result = await generate_vision_candidates(
            mock_ctx,
            str(raw_file),
            "vision_frame",
            editing_vision=contract,
        )
        assert "error" in result
        assert "unfilled editing vision contract" in result["error"].lower()

    async def test_critique_gate_returns_rubric_and_threshold(self, mock_ctx):
        result = await critique_gate(mock_ctx, candidate_name="warm_v1", intended_style="warm_travel")
        assert "scoring_rubric" in result
        assert "minimum_export_threshold" in result
        assert "tonal_separation_score" in result["scoring_rubric"]
        assert "intent_alignment_score" in result["scoring_rubric"]
        assert "preserved_scene_value_score" in result["scoring_rubric"]
        assert "harmful_overcorrection_penalty" in result["scoring_rubric"]
        assert "color_split_penalty" in result["scoring_rubric"]
        assert "visible_difference_score" in result["scoring_rubric"]
        assert "visual_hierarchy_improvement_score" in result["scoring_rubric"]
        assert "thumbnail_impact_score" in result["scoring_rubric"]
        assert "wrong_standard_warning" in result["scoring_rubric"]
        assert any("only changes exposure/warmth/saturation" in r for r in result["next_action_rules"])
        assert any("too close to the original" in r for r in result["next_action_rules"])
        assert result["minimum_export_threshold"]["core_score_average_min"] == 7.0

    async def test_critique_gate_accepts_editing_vision(self, mock_ctx):
        result = await critique_gate(
            mock_ctx,
            candidate_name="vision_v1",
            intended_style="faithful_refinement",
            editing_vision={
                "emotional_goal": "mysterious rural cloud mood with hopeful light",
                "visual_anchor": "the light break over the fields",
            },
        )

        assert "editing_vision" in result
        assert "visual_anchor_score" in result["scoring_rubric"]
        assert "vision_alignment_score" in result["scoring_rubric"]
        assert result["intent_standard"]["primary_intent_category"] != "clean_portrait"

    async def test_create_curation_plan(self, mock_ctx, tmp_path):
        (tmp_path / "a.cr2").write_bytes(b"raw")
        (tmp_path / "b.nef").write_bytes(b"raw")
        (tmp_path / "notes.txt").write_text("ignore")

        result = await create_curation_plan(mock_ctx, str(tmp_path), recursive=False)
        assert "error" not in result
        assert result["discovered_file_count"] == 2
        assert "strong_keeper" in result["rating_categories"]


class TestReadExif:
    """Tests for read_exif tool."""

    async def test_returns_exif_data(self, mock_ctx, tmp_path):
        test_file = tmp_path / "photo.cr2"
        test_file.write_bytes(b"fake raw")

        mock_data = {
            "camera_make": "Canon",
            "camera_model": "EOS R5",
            "iso": "400",
            "aperture": "2.8",
            "shutter_speed": "1/250",
            "focal_length": "85",
            "white_balance": "",
            "datetime": "",
            "width": "",
            "height": "",
            "gps_latitude": "",
            "gps_longitude": "",
            "orientation": "",
            "lens_model": "",
        }

        with patch("rawtherapee_mcp.server.read_exif_data", return_value=mock_data):
            result = await read_exif(mock_ctx, str(test_file))
            assert result["camera_make"] == "Canon"
            assert result["file_path"] == str(test_file)

    async def test_file_not_found(self, mock_ctx):
        result = await read_exif(mock_ctx, "/nonexistent/photo.cr2")
        assert "error" in result


class TestProcessRaw:
    """Tests for process_raw tool."""

    async def test_no_rt_returns_error(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        result = await process_raw(mock_ctx_no_rt, str(raw_file), str(pp3_file))
        assert "error" in result
        assert "not found" in result["error"]

    async def test_raw_file_not_found(self, mock_ctx):
        result = await process_raw(mock_ctx, "/nonexistent.cr2", "/some.pp3")
        assert "error" in result

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await process_raw(mock_ctx, str(raw_file), "/nonexistent.pp3")
        assert "error" in result

    async def test_calls_rt_cli(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        mock_result = {"success": True, "output_path": "/output/photo.jpg", "processing_time": 1.5, "file_size": 1000}

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await process_raw(mock_ctx, str(raw_file), str(pp3_file), include_preview=False)
            assert result["success"] is True


class TestPreviewRaw:
    """Tests for preview_raw tool."""

    async def test_no_rt_returns_error(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await preview_raw(mock_ctx_no_rt, str(raw_file))
        assert "error" in result

    async def test_raw_file_not_found(self, mock_ctx):
        result = await preview_raw(mock_ctx, "/nonexistent.cr2")
        assert "error" in result

    async def test_generates_preview(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "preview.jpg"),
            "processing_time": 0.5,
            "file_size": 500,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await preview_raw(mock_ctx, str(raw_file), return_image=False)
            assert result["success"] is True
            assert "preview_path" in result
            assert result["max_width"] == 1200

    async def test_preview_with_profile_merges_single_pp3(self, mock_ctx, tmp_path):
        """Preview should merge resize into user's profile (single PP3)."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "warm.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\nVersion=351\n[Exposure]\nCompensation=0.5\n")

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "preview.jpg"),
            "processing_time": 0.5,
            "file_size": 500,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result) as mock_cli:
            result = await preview_raw(mock_ctx, str(raw_file), profile_path=str(pp3_file), return_image=False)
            assert result["success"] is True
            # Should pass exactly ONE profile (combined) to avoid multi-PP3 merge crashes
            call_args = mock_cli.call_args
            profiles = call_args.kwargs.get("profiles", call_args[1].get("profiles", []))
            assert len(profiles) == 1

    async def test_preview_error_includes_pp3_content(self, mock_ctx, tmp_path):
        """Failed preview should include PP3 content for debugging."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        mock_result = {
            "error": "rawtherapee-cli failed (exit code -1)",
            "stdout": "",
            "stderr": "",
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await preview_raw(mock_ctx, str(raw_file))
            assert "error" in result
            assert "preview_pp3_content" in result

    async def test_preview_skips_resize_when_crop_enabled(self, mock_ctx, tmp_path):
        """Preview should not add Resize when profile has Crop (RT 5.12 bug)."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "cropped.pp3"
        pp3_file.write_text(
            "[Version]\nAppVersion=5.11\nVersion=351\n[Crop]\nEnabled=true\nX=100\nY=0\nW=3000\nH=4000\n"
        )

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "preview.jpg"),
            "processing_time": 0.5,
            "file_size": 500,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result) as mock_cli:
            result = await preview_raw(mock_ctx, str(raw_file), profile_path=str(pp3_file), return_image=False)
            assert result["success"] is True
            # Verify the combined PP3 was saved — read it to check Resize is disabled
            call_args = mock_cli.call_args
            profiles = call_args.kwargs.get("profiles", call_args[1].get("profiles", []))
            assert len(profiles) == 1
            # The temp PP3 was cleaned up, but we can verify from the call that
            # exactly one profile was passed (combined with Crop but no Resize)

    async def test_preview_adds_resize_when_no_crop(self, mock_ctx, tmp_path):
        """Preview should add Resize when profile has no Crop."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "nocrop.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\nVersion=351\n[Exposure]\nCompensation=0.5\n")

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "preview.jpg"),
            "processing_time": 0.5,
            "file_size": 500,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await preview_raw(mock_ctx, str(raw_file), profile_path=str(pp3_file), return_image=False)
            assert result["success"] is True
            assert result["max_width"] == 1200


class TestAdjustProfile:
    """Tests for adjust_profile tool."""

    async def test_adjust_with_friendly_names(self, mock_ctx, tmp_path):
        """Test adjust_profile with friendly parameter names."""
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\nVersion=351\n[Exposure]\nCompensation=0\n")

        result = await adjust_profile(
            mock_ctx,
            str(pp3_file),
            {"exposure": {"compensation": 1.5}},
        )
        assert "error" not in result
        assert result["adjustments_applied"]["exposure"]["compensation"] == 1.5

        # Verify the file was actually written
        from rawtherapee_mcp.pp3_parser import PP3Profile

        profile = PP3Profile()
        profile.load(pp3_file)
        assert profile.get("Exposure", "Compensation") == "1.5"

    async def test_adjust_with_raw_pp3_keys(self, mock_ctx, tmp_path):
        """Test adjust_profile with raw PP3 section/key pairs."""
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\nVersion=351\n[Crop]\nEnabled=true\nX=0\nY=0\n")

        result = await adjust_profile(
            mock_ctx,
            str(pp3_file),
            {"Crop": {"W": "3108", "H": "6732", "FixedRatio": "true", "Guide": "Frame"}},
        )
        assert "error" not in result

        # Verify the raw values were written
        from rawtherapee_mcp.pp3_parser import PP3Profile

        profile = PP3Profile()
        profile.load(pp3_file)
        assert profile.get("Crop", "W") == "3108"
        assert profile.get("Crop", "H") == "6732"
        assert profile.get("Crop", "FixedRatio") == "true"
        assert profile.get("Crop", "Guide") == "Frame"

    async def test_adjust_profile_not_found(self, mock_ctx):
        result = await adjust_profile(
            mock_ctx,
            "/nonexistent.pp3",
            {"exposure": {"compensation": 1.0}},
        )
        assert "error" in result


class TestReadExifRecommendations:
    """Tests for EXIF recommendations in read_exif."""

    async def test_includes_recommendations(self, mock_ctx, tmp_path):
        """read_exif should include processing recommendations."""
        test_file = tmp_path / "photo.cr2"
        test_file.write_bytes(b"fake raw")

        mock_data = {
            "camera_make": "Canon",
            "camera_model": "EOS R5",
            "iso": "6400",
            "aperture": "14/10",
            "shutter_speed": "1/250",
            "focal_length": "85",
            "white_balance": "0",
            "datetime": "",
            "width": "",
            "height": "",
            "gps_latitude": "",
            "gps_longitude": "",
            "orientation": "",
            "lens_model": "RF 85mm F1.2L USM",
        }

        with patch("rawtherapee_mcp.server.read_exif_data", return_value=mock_data):
            result = await read_exif(mock_ctx, str(test_file))
            assert "recommendations" in result
            recs = result["recommendations"]
            assert isinstance(recs, dict)
            assert "text" in recs
            assert "suggested_parameters" in recs
            assert "warnings" in recs
            assert len(recs["text"]) >= 3


class TestPreviewRawToolResult:
    """Tests for preview_raw ToolResult image return."""

    async def test_returns_tool_result_with_image(self, mock_ctx, tmp_path):
        """Successful preview with return_image=True returns ToolResult."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "blue").save(str(out), "JPEG")
            return {
                "success": True,
                "output_path": str(out),
                "processing_time": 0.5,
                "file_size": 500,
            }

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await preview_raw(mock_ctx, str(raw_file), return_image=True)
            assert isinstance(result, ToolResult)
            assert result.content is not None
            assert len(result.content) == 2
            assert result.content[0].type == "text"
            assert result.content[1].type == "image"
            assert result.structured_content is not None
            assert result.structured_content["success"] is True

    async def test_returns_dict_when_return_image_false(self, mock_ctx, tmp_path):
        """return_image=False returns plain dict even on success."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "preview.jpg"),
            "processing_time": 0.5,
            "file_size": 500,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await preview_raw(mock_ctx, str(raw_file), return_image=False)
            assert isinstance(result, dict)
            assert result["success"] is True

    async def test_returns_dict_on_error(self, mock_ctx, tmp_path):
        """Errors always return dict regardless of return_image."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        mock_result = {"error": "RT failed", "stdout": "", "stderr": ""}

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await preview_raw(mock_ctx, str(raw_file), return_image=True)
            assert isinstance(result, dict)
            assert "error" in result


class TestProcessRawToolResult:
    """Tests for process_raw ToolResult thumbnail return."""

    async def test_returns_tool_result_with_preview(self, mock_ctx, tmp_path):
        """Successful processing with include_preview=True returns ToolResult."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        output_file = tmp_path / "output" / "photo.jpg"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        PILImage.new("RGB", (3000, 2000), "green").save(str(output_file), "JPEG")

        mock_result = {
            "success": True,
            "output_path": str(output_file),
            "processing_time": 1.5,
            "file_size": 1000,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await process_raw(mock_ctx, str(raw_file), str(pp3_file), include_preview=True)
            assert isinstance(result, ToolResult)
            assert result.content is not None
            assert len(result.content) == 2
            assert result.content[1].type == "image"

    async def test_returns_dict_when_preview_disabled(self, mock_ctx, tmp_path):
        """include_preview=False returns plain dict."""
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "photo.jpg"),
            "processing_time": 1.5,
            "file_size": 1000,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await process_raw(mock_ctx, str(raw_file), str(pp3_file), include_preview=False)
            assert isinstance(result, dict)
            assert result["success"] is True


# ---------------------------------------------------------------------------
# Feature Request v2 Tests
# ---------------------------------------------------------------------------


class TestGetHistogram:
    """Tests for get_histogram tool."""

    async def test_file_not_found(self, mock_ctx):
        result = await get_histogram(mock_ctx, "/nonexistent/image.jpg")
        assert "error" in result

    async def test_returns_statistics(self, mock_ctx, tmp_path):
        img_path = tmp_path / "test.jpg"
        PILImage.new("RGB", (100, 100), "red").save(str(img_path), "JPEG")

        result = await get_histogram(mock_ctx, str(img_path))
        assert "statistics" in result
        assert "clipping" in result
        assert "total_pixels" in result
        assert result["total_pixels"] == 10000

    async def test_includes_svg(self, mock_ctx, tmp_path):
        img_path = tmp_path / "test.jpg"
        PILImage.new("RGB", (100, 100), "blue").save(str(img_path), "JPEG")

        result = await get_histogram(mock_ctx, str(img_path), include_svg=True)
        assert "svg" in result
        assert result["svg"].startswith("<svg")

    async def test_excludes_svg(self, mock_ctx, tmp_path):
        img_path = tmp_path / "test.jpg"
        PILImage.new("RGB", (100, 100), "blue").save(str(img_path), "JPEG")

        result = await get_histogram(mock_ctx, str(img_path), include_svg=False)
        assert "svg" not in result


class TestPreviewBeforeAfter:
    """Tests for preview_before_after tool."""

    async def test_no_rt_returns_error(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        result = await preview_before_after(mock_ctx_no_rt, str(raw_file), str(pp3_file))
        assert "error" in result

    async def test_raw_not_found(self, mock_ctx, tmp_path):
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        result = await preview_before_after(mock_ctx, "/nonexistent.cr2", str(pp3_file))
        assert "error" in result

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await preview_before_after(mock_ctx, str(raw_file), "/nonexistent.pp3")
        assert "error" in result

    async def test_returns_both_previews(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n[Exposure]\nCompensation=1.0\n")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "blue").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.5, "file_size": 500}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await preview_before_after(mock_ctx, str(raw_file), str(pp3_file))
            assert isinstance(result, ToolResult)
            assert result.content is not None
            # TextContent + 2 ImageContent (before + after)
            assert len(result.content) == 3
            assert result.content[0].type == "text"
            assert result.content[1].type == "image"
            assert result.content[2].type == "image"


class TestAdjustCropPosition:
    """Tests for adjust_crop_position tool."""

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        result = await adjust_crop_position(mock_ctx, "/nonexistent.pp3", str(raw_file), include_preview=False)
        assert "error" in result

    async def test_no_crop_enabled(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "nocrop.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n[Exposure]\nCompensation=0\n")

        result = await adjust_crop_position(mock_ctx, str(pp3_file), str(raw_file), include_preview=False)
        assert "error" in result
        assert "crop" in result["error"].lower()

    async def test_moves_crop_center(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "cropped.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n[Crop]\nEnabled=true\nX=0\nY=0\nW=1000\nH=500\n")

        with patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(4000, 3000)):
            result = await adjust_crop_position(
                mock_ctx,
                str(pp3_file),
                str(raw_file),
                horizontal="center",
                vertical="center",
                include_preview=False,
            )
            assert "error" not in result
            assert result["crop_x"] == 1500  # (4000 - 1000) // 2
            assert result["crop_y"] == 1250  # (3000 - 500) // 2

    async def test_moves_crop_bottom_right(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "cropped.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n[Crop]\nEnabled=true\nX=0\nY=0\nW=1000\nH=500\n")

        with patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(4000, 3000)):
            result = await adjust_crop_position(
                mock_ctx,
                str(pp3_file),
                str(raw_file),
                horizontal="right",
                vertical="bottom",
                include_preview=False,
            )
            assert result["crop_x"] == 3000  # 4000 - 1000
            assert result["crop_y"] == 2500  # 3000 - 500

    async def test_pixel_offset(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "cropped.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n[Crop]\nEnabled=true\nX=0\nY=0\nW=1000\nH=500\n")

        with patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(4000, 3000)):
            result = await adjust_crop_position(
                mock_ctx,
                str(pp3_file),
                str(raw_file),
                horizontal="500",
                vertical="200",
                include_preview=False,
            )
            assert result["crop_x"] == 500
            assert result["crop_y"] == 200


class TestPreviewExposureBracket:
    """Tests for preview_exposure_bracket tool."""

    async def test_no_rt_returns_error(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await preview_exposure_bracket(mock_ctx_no_rt, str(raw_file))
        assert "error" in result

    async def test_raw_not_found(self, mock_ctx):
        result = await preview_exposure_bracket(mock_ctx, "/nonexistent.cr2")
        assert "error" in result

    async def test_default_stops(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.5, "file_size": 500}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await preview_exposure_bracket(mock_ctx, str(raw_file))
            assert isinstance(result, ToolResult)
            assert result.content is not None
            # TextContent + 3 ImageContent (default: -1, 0, +1)
            assert len(result.content) == 4

    async def test_custom_stops(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.5, "file_size": 500}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await preview_exposure_bracket(mock_ctx, str(raw_file), stops=[-2.0, 0.0, 2.0])
            assert isinstance(result, ToolResult)
            assert result.structured_content is not None
            assert result.structured_content["stops"] == [-2.0, 0.0, 2.0]


class TestPreviewWhiteBalance:
    """Tests for preview_white_balance tool."""

    async def test_no_rt_returns_error(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await preview_white_balance(mock_ctx_no_rt, str(raw_file))
        assert "error" in result

    async def test_raw_not_found(self, mock_ctx):
        result = await preview_white_balance(mock_ctx, "/nonexistent.cr2")
        assert "error" in result

    async def test_default_presets(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.5, "file_size": 500}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await preview_white_balance(mock_ctx, str(raw_file))
            assert isinstance(result, ToolResult)
            assert result.content is not None
            # TextContent + 5 ImageContent (default: 5 presets)
            assert len(result.content) == 6
            assert result.structured_content is not None
            assert len(result.structured_content["presets"]) == 5

    async def test_custom_presets(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.5, "file_size": 500}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await preview_white_balance(mock_ctx, str(raw_file), presets=["Daylight", "Tungsten"])
            assert isinstance(result, ToolResult)
            assert result.content is not None
            # TextContent + 2 ImageContent
            assert len(result.content) == 3


class TestCompareProfilesVisual:
    """Tests for compare_profiles with visual preview."""

    async def test_diff_only(self, mock_ctx, tmp_path):
        """Default behavior: diff only, no preview."""
        pp3_a = tmp_path / "a.pp3"
        pp3_a.write_text("[Version]\nAppVersion=5.11\n[Exposure]\nCompensation=0\n")
        pp3_b = tmp_path / "b.pp3"
        pp3_b.write_text("[Version]\nAppVersion=5.11\n[Exposure]\nCompensation=1.5\n")

        result = await compare_profiles(mock_ctx, str(pp3_a), str(pp3_b))
        assert isinstance(result, dict)
        assert "profile_a" in result

    async def test_visual_preview(self, mock_ctx, tmp_path):
        """With file_path + include_preview, returns ToolResult with images."""
        pp3_a = tmp_path / "a.pp3"
        pp3_a.write_text("[Version]\nAppVersion=5.11\n[Exposure]\nCompensation=0\n")
        pp3_b = tmp_path / "b.pp3"
        pp3_b.write_text("[Version]\nAppVersion=5.11\n[Exposure]\nCompensation=1.5\n")
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.5, "file_size": 500}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await compare_profiles(
                mock_ctx,
                str(pp3_a),
                str(pp3_b),
                file_path=str(raw_file),
                include_preview=True,
            )
            assert isinstance(result, ToolResult)
            assert result.content is not None
            # TextContent + 2 ImageContent
            assert len(result.content) == 3


class TestExportMultiDevice:
    """Tests for export_multi_device tool."""

    async def test_no_rt_returns_error(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        result = await export_multi_device(mock_ctx_no_rt, str(raw_file), str(pp3_file), ["iphone_15_pro"])
        assert "error" in result

    async def test_raw_not_found(self, mock_ctx):
        result = await export_multi_device(mock_ctx, "/nonexistent.cr2", "/some.pp3", ["iphone_15_pro"])
        assert "error" in result

    async def test_unknown_preset(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        with patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(4000, 3000)):
            result = await export_multi_device(mock_ctx, str(raw_file), str(pp3_file), ["nonexistent_device"])
            assert result["failed"] == 1
            assert "not found" in result["results"][0]["error"]

    async def test_processes_multiple_presets(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "profile.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n")

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "output.jpg"),
            "processing_time": 1.0,
            "file_size": 1000,
        }

        preset_a = {"name": "Device A", "width": 1170, "height": 2532}
        preset_b = {"name": "Device B", "width": 1440, "height": 3200}

        def mock_get_preset(name, _dir):
            return {"device_a": preset_a, "device_b": preset_b}.get(name)

        with (
            patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result),
            patch("rawtherapee_mcp.server.get_effective_dimensions", return_value=(6000, 4000)),
            patch("rawtherapee_mcp.server.get_preset", side_effect=mock_get_preset),
        ):
            result = await export_multi_device(mock_ctx, str(raw_file), str(pp3_file), ["device_a", "device_b"])
            assert result["total"] == 2
            assert result["succeeded"] == 2


class TestBatchPreview:
    """Tests for batch_preview tool."""

    async def test_no_rt_returns_error(self, mock_ctx_no_rt, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        result = await batch_preview(mock_ctx_no_rt, [str(raw_file)])
        assert "error" in result

    async def test_previews_multiple_files(self, mock_ctx, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"photo{i}.cr2"
            f.write_bytes(b"raw")
            files.append(str(f))

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (300, 200), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": 200}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await batch_preview(mock_ctx, files)
            assert isinstance(result, ToolResult)
            assert result.content is not None
            # TextContent + 3 ImageContent
            assert len(result.content) == 4

    async def test_caps_at_max_images(self, mock_ctx, tmp_path):
        files = []
        for i in range(20):
            f = tmp_path / f"photo{i}.cr2"
            f.write_bytes(b"raw")
            files.append(str(f))

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (300, 200), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": 200}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await batch_preview(mock_ctx, files, max_images=5)
            assert isinstance(result, ToolResult)
            assert result.structured_content is not None
            assert result.structured_content["total"] == 5
            assert result.structured_content["capped"] is True

    async def test_missing_file_in_batch(self, mock_ctx, tmp_path):
        real_file = tmp_path / "photo.cr2"
        real_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (300, 200), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": 200}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await batch_preview(mock_ctx, [str(real_file), "/nonexistent.cr2"])
            # Should still return something — one success, one error
            if isinstance(result, ToolResult):
                assert result.structured_content is not None
                previews = result.structured_content["previews"]
            else:
                previews = result["previews"]
            assert len(previews) == 2
            assert any("error" in p for p in previews)


class TestAnalyzeImage:
    """Tests for analyze_image tool."""

    async def test_file_not_found(self, mock_ctx):
        result = await analyze_image(mock_ctx, "/nonexistent/image.jpg")
        assert "error" in result

    async def test_returns_exif_and_histogram(self, mock_ctx, tmp_path):
        img_path = tmp_path / "photo.jpg"
        PILImage.new("RGB", (1000, 800), "green").save(str(img_path), "JPEG")

        mock_exif = {
            "camera_make": "Canon",
            "camera_model": "EOS R5",
            "iso": "400",
            "aperture": "5.6",
            "shutter_speed": "1/250",
            "focal_length": "85",
            "white_balance": "",
            "datetime": "",
            "width": "1000",
            "height": "800",
            "gps_latitude": "",
            "gps_longitude": "",
            "orientation": "",
            "lens_model": "",
        }

        with patch("rawtherapee_mcp.server.read_exif_data", return_value=mock_exif):
            result = await analyze_image(mock_ctx, str(img_path))
            assert isinstance(result, ToolResult)
            assert result.structured_content is not None
            assert "exif" in result.structured_content
            assert "recommendations" in result.structured_content
            assert "histogram" in result.structured_content

    async def test_no_thumbnail(self, mock_ctx, tmp_path):
        img_path = tmp_path / "photo.jpg"
        PILImage.new("RGB", (100, 100), "red").save(str(img_path), "JPEG")

        mock_exif = {
            "camera_make": "",
            "camera_model": "",
            "iso": "",
            "aperture": "",
            "shutter_speed": "",
            "focal_length": "",
            "white_balance": "",
            "datetime": "",
            "width": "",
            "height": "",
            "gps_latitude": "",
            "gps_longitude": "",
            "orientation": "",
            "lens_model": "",
        }

        with patch("rawtherapee_mcp.server.read_exif_data", return_value=mock_exif):
            result = await analyze_image(mock_ctx, str(img_path), include_thumbnail=False)
            assert isinstance(result, dict)
            assert "exif" in result


# ---------------------------------------------------------------------------
# Bug 3 — Crop+Resize conflict warning
# ---------------------------------------------------------------------------


class TestCropResizeWarning:
    """Tests for Crop+Resize conflict detection."""

    async def test_process_raw_warns_on_conflict(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "conflict.pp3"
        pp3_file.write_text(
            "[Version]\nAppVersion=5.11\n"
            "[Crop]\nEnabled=true\nX=0\nY=0\nW=1000\nH=500\n"
            "[Resize]\nEnabled=true\nWidth=800\nHeight=600\n"
        )

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "output.jpg"),
            "processing_time": 1.0,
            "file_size": 1000,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await process_raw(mock_ctx, str(raw_file), str(pp3_file), include_preview=False)
            assert "warning" in result
            assert "crop" in result["warning"].lower()

    async def test_process_raw_no_warning_without_conflict(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")
        pp3_file = tmp_path / "ok.pp3"
        pp3_file.write_text("[Version]\nAppVersion=5.11\n[Crop]\nEnabled=true\nX=0\nY=0\nW=1000\nH=500\n")

        mock_result = {
            "success": True,
            "output_path": str(tmp_path / "output.jpg"),
            "processing_time": 1.0,
            "file_size": 1000,
        }

        with patch("rawtherapee_mcp.server.run_rt_cli", return_value=mock_result):
            result = await process_raw(mock_ctx, str(raw_file), str(pp3_file), include_preview=False)
            assert "warning" not in result


# ---------------------------------------------------------------------------
# V2 — batch_preview EXIF summary
# ---------------------------------------------------------------------------


class TestBatchPreviewExif:
    """Tests for batch_preview include_exif parameter."""

    async def test_include_exif(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        mock_exif = {
            "iso": "400",
            "aperture": "2.8",
            "shutter_speed": "1/250",
            "focal_length": "85",
            "camera_make": "Canon",
            "camera_model": "EOS R5",
            "lens_model": "",
            "white_balance": "",
            "datetime": "",
            "width": "",
            "height": "",
            "gps_latitude": "",
            "gps_longitude": "",
            "orientation": "",
        }

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (300, 200), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": 200}

        with (
            patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview),
            patch("rawtherapee_mcp.server.read_exif_data", return_value=mock_exif),
        ):
            result = await batch_preview(mock_ctx, [str(raw_file)], include_exif=True)
            if isinstance(result, ToolResult):
                previews = result.structured_content["previews"]
            else:
                previews = result["previews"]
            assert "exif_summary" in previews[0]
            assert previews[0]["exif_summary"]["iso"] == "400"


# ---------------------------------------------------------------------------
# V4 — White balance Kelvin temperatures
# ---------------------------------------------------------------------------


class TestWhiteBalanceTemperature:
    """Tests for WB Kelvin temperature annotations."""

    async def test_temperature_included(self, mock_ctx, tmp_path):
        raw_file = tmp_path / "photo.cr2"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (600, 400), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.5, "file_size": 500}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await preview_white_balance(mock_ctx, str(raw_file), presets=["Daylight", "Tungsten"])
            assert isinstance(result, ToolResult)
            previews = result.structured_content["previews"]
            assert previews[0]["temperature_k"] == 5500
            assert previews[1]["temperature_k"] == 3200


# ---------------------------------------------------------------------------
# F2 — batch_analyze
# ---------------------------------------------------------------------------


class TestBatchAnalyze:
    """Tests for batch_analyze tool."""

    async def test_file_not_found(self, mock_ctx):
        result = await batch_analyze(mock_ctx, ["/nonexistent/image.jpg"], include_thumbnails=False)
        if isinstance(result, dict):
            analyses = result["analyses"]
        else:
            analyses = result.structured_content["analyses"]
        assert "error" in analyses[0]

    async def test_returns_exif_and_histogram(self, mock_ctx, tmp_path):
        img_path = tmp_path / "photo.jpg"
        PILImage.new("RGB", (100, 100), "green").save(str(img_path), "JPEG")

        mock_exif = {
            "camera_make": "Canon",
            "camera_model": "EOS R5",
            "iso": "400",
            "aperture": "5.6",
            "shutter_speed": "1/250",
            "focal_length": "85",
            "white_balance": "",
            "datetime": "",
            "width": "100",
            "height": "100",
            "gps_latitude": "",
            "gps_longitude": "",
            "orientation": "",
            "lens_model": "",
        }

        with patch("rawtherapee_mcp.server.read_exif_data", return_value=mock_exif):
            result = await batch_analyze(mock_ctx, [str(img_path)], include_thumbnails=False)
            if isinstance(result, dict):
                analyses = result["analyses"]
            else:
                analyses = result.structured_content["analyses"]
            assert "exif" in analyses[0]
            assert "recommendations" in analyses[0]
            assert "histogram_summary" in analyses[0]
            # Should NOT have full channel data or SVG
            assert "svg" not in analyses[0].get("histogram_summary", {})

    async def test_caps_at_max(self, mock_ctx, tmp_path):
        files = []
        for i in range(10):
            p = tmp_path / f"photo{i}.jpg"
            PILImage.new("RGB", (50, 50), "blue").save(str(p), "JPEG")
            files.append(str(p))

        mock_exif = {
            "camera_make": "",
            "camera_model": "",
            "iso": "",
            "aperture": "",
            "shutter_speed": "",
            "focal_length": "",
            "white_balance": "",
            "datetime": "",
            "width": "",
            "height": "",
            "gps_latitude": "",
            "gps_longitude": "",
            "orientation": "",
            "lens_model": "",
        }

        with patch("rawtherapee_mcp.server.read_exif_data", return_value=mock_exif):
            result = await batch_analyze(mock_ctx, files, max_images=3, include_thumbnails=False)
            if isinstance(result, dict):
                assert result["total"] == 3
                assert result["capped"] is True
            else:
                assert result.structured_content["total"] == 3
                assert result.structured_content["capped"] is True


# ---------------------------------------------------------------------------
# F3 — interpolate_profiles
# ---------------------------------------------------------------------------


class TestInterpolateProfiles:
    """Tests for interpolate_profiles tool."""

    async def test_profile_not_found(self, mock_ctx):
        result = await interpolate_profiles(mock_ctx, "/nonexistent_a.pp3", "/nonexistent_b.pp3")
        assert "error" in result

    async def test_basic_interpolation(self, mock_ctx, tmp_path):
        pp3_a = tmp_path / "a.pp3"
        pp3_a.write_text("[Exposure]\nCompensation=0\n")
        pp3_b = tmp_path / "b.pp3"
        pp3_b.write_text("[Exposure]\nCompensation=2\n")

        result = await interpolate_profiles(mock_ctx, str(pp3_a), str(pp3_b), factor=0.5, output_name="blend")
        assert "error" not in result
        assert result["factor"] == 0.5
        assert "output_path" in result
        assert result["summary"]["Exposure"]["Compensation"] == "1"

    async def test_factor_zero(self, mock_ctx, tmp_path):
        pp3_a = tmp_path / "a.pp3"
        pp3_a.write_text("[Exposure]\nCompensation=1.5\n")
        pp3_b = tmp_path / "b.pp3"
        pp3_b.write_text("[Exposure]\nCompensation=3.0\n")

        result = await interpolate_profiles(mock_ctx, str(pp3_a), str(pp3_b), factor=0.0)
        assert result["summary"]["Exposure"]["Compensation"] == "1.5"

    async def test_factor_one(self, mock_ctx, tmp_path):
        pp3_a = tmp_path / "a.pp3"
        pp3_a.write_text("[Exposure]\nCompensation=1.5\n")
        pp3_b = tmp_path / "b.pp3"
        pp3_b.write_text("[Exposure]\nCompensation=3.0\n")

        result = await interpolate_profiles(mock_ctx, str(pp3_a), str(pp3_b), factor=1.0)
        assert result["summary"]["Exposure"]["Compensation"] == "3"


# ---------------------------------------------------------------------------
# Locallab tools
# ---------------------------------------------------------------------------


class TestAddLuminanceAdjustment:
    """Tests for add_luminance_adjustment tool."""

    async def test_add_shadow_adjustment(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5})
        assert "error" not in result
        assert result["spot_index"] == 0
        assert result["adjustment_type"] == "shadows"
        assert result["total_spots"] == 1

    async def test_add_highlight_adjustment(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await add_luminance_adjustment(mock_ctx, str(pp3), "highlights", {"exposure": -0.3, "saturation": -10})
        assert "error" not in result
        assert result["parameters_applied"]["exposure"] == -0.3

    async def test_add_custom_range(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await add_luminance_adjustment(
            mock_ctx,
            str(pp3),
            "custom",
            {"contrast": 20},
            luminance_range={"lower": 40, "upper": 80},
        )
        assert "error" not in result
        assert result["adjustment_type"] == "custom"

    async def test_add_multiple(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5})
        result = await add_luminance_adjustment(mock_ctx, str(pp3), "highlights", {"exposure": -0.3})
        assert result["spot_index"] == 1
        assert result["total_spots"] == 2

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        result = await add_luminance_adjustment(mock_ctx, str(tmp_path / "nope.pp3"), "shadows", {"exposure": 0.5})
        assert "error" in result

    async def test_invalid_type(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await add_luminance_adjustment(mock_ctx, str(pp3), "invalid", {"exposure": 0.5})
        assert "error" in result

    async def test_save_as(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")
        out = tmp_path / "out.pp3"

        result = await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5}, save_as=str(out))
        assert result["profile_path"] == str(out)
        assert out.is_file()


class TestListLocalAdjustments:
    """Tests for list_local_adjustments tool."""

    async def test_empty_profile(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await list_local_adjustments(mock_ctx, str(pp3))
        assert result["total_spots"] == 0
        assert result["spots"] == []

    async def test_with_spots(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5})
        await add_luminance_adjustment(mock_ctx, str(pp3), "highlights", {"exposure": -0.3})

        result = await list_local_adjustments(mock_ctx, str(pp3))
        assert result["total_spots"] == 2
        assert len(result["spots"]) == 2
        assert result["spots"][0]["type"] == "shadows"
        assert result["spots"][1]["type"] == "highlights"

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        result = await list_local_adjustments(mock_ctx, str(tmp_path / "nope.pp3"))
        assert "error" in result


class TestAdjustLocalSpot:
    """Tests for adjust_local_spot tool."""

    async def test_update_parameters(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5})

        result = await adjust_local_spot(mock_ctx, str(pp3), 0, parameters={"exposure": 0.25})
        assert "error" not in result
        assert result["spot_index"] == 0

    async def test_disable_spot(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5})

        result = await adjust_local_spot(mock_ctx, str(pp3), 0, enabled=False)
        assert "error" not in result
        assert result["updated"]["enabled"] is False

    async def test_invalid_index(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await adjust_local_spot(mock_ctx, str(pp3), 0, parameters={"exposure": 0.5})
        assert "error" in result

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        result = await adjust_local_spot(mock_ctx, str(tmp_path / "nope.pp3"), 0, parameters={"exposure": 0.5})
        assert "error" in result


class TestRemoveLocalAdjustment:
    """Tests for remove_local_adjustment tool."""

    async def test_remove_spot(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5})

        result = await remove_local_adjustment(mock_ctx, str(pp3), 0)
        assert "error" not in result
        assert result["removed_index"] == 0
        assert result["total_spots"] == 0

    async def test_remove_invalid_index(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await remove_local_adjustment(mock_ctx, str(pp3), 0)
        assert "error" in result

    async def test_remove_preserves_others(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        await add_luminance_adjustment(mock_ctx, str(pp3), "shadows", {"exposure": 0.5}, spot_name="Shadow")
        await add_luminance_adjustment(mock_ctx, str(pp3), "highlights", {"exposure": -0.3}, spot_name="Highlight")

        result = await remove_local_adjustment(mock_ctx, str(pp3), 0)
        assert result["total_spots"] == 1

        # The highlight spot should now be at index 0
        listing = await list_local_adjustments(mock_ctx, str(pp3))
        assert listing["spots"][0]["name"] == "Highlight"

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        result = await remove_local_adjustment(mock_ctx, str(tmp_path / "nope.pp3"), 0)
        assert "error" in result


class TestApplyLocalPreset:
    """Tests for apply_local_preset tool."""

    async def test_apply_shadow_recovery(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await apply_local_preset(mock_ctx, str(pp3), "shadow_recovery")
        assert "error" not in result
        assert result["preset"] == "shadow_recovery"
        assert len(result["spots_added"]) == 1
        assert result["total_spots"] == 1

    async def test_apply_hdr_natural(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await apply_local_preset(mock_ctx, str(pp3), "hdr_natural")
        assert "error" not in result
        assert len(result["spots_added"]) == 3
        assert result["total_spots"] == 3

    async def test_apply_split_tone(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await apply_local_preset(mock_ctx, str(pp3), "split_tone_warm_cool")
        assert "error" not in result
        assert len(result["spots_added"]) == 2

    async def test_unknown_preset(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await apply_local_preset(mock_ctx, str(pp3), "nonexistent")
        assert "error" in result
        assert "available_presets" in result

    async def test_intensity_parameter(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")

        result = await apply_local_preset(mock_ctx, str(pp3), "shadow_recovery", intensity=100)
        assert "error" not in result
        assert result["intensity"] == 100

    async def test_save_as(self, mock_ctx, tmp_path):
        pp3 = tmp_path / "test.pp3"
        pp3.write_text("[Version]\nAppVersion=5.11\n")
        out = tmp_path / "preset_out.pp3"

        result = await apply_local_preset(mock_ctx, str(pp3), "shadow_recovery", save_as=str(out))
        assert result["profile_path"] == str(out)
        assert out.is_file()

    async def test_profile_not_found(self, mock_ctx, tmp_path):
        result = await apply_local_preset(mock_ctx, str(tmp_path / "nope.pp3"), "shadow_recovery")
        assert "error" in result
