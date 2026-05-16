"""Tests for Phase 10 manifest-select planning and prepare flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastmcp.tools import ToolResult
from PIL import Image as PILImage

from rawtherapee_mcp.control_policy import build_agent_manifest_summary
from rawtherapee_mcp.predictive_editor import build_manifest_select_edit_plan
from rawtherapee_mcp.server import (
    auto_edit_manifest_select_prepare,
    auto_edit_predictive,
    verify_predictive_edit,
)


def _valid_edit_plan() -> dict[str, object]:
    return {
        "image_observation": {
            "main_subject": "tram",
            "supporting_elements": ["rails"],
            "distractions": ["poles"],
            "tonal_state": "slightly flat",
            "color_state": "muted",
            "highlight_shadow_state": "safe",
            "composition_state": "already strong",
        },
        "vision_interpretation": {
            "user_goal": "make the tram read faster",
            "desired_viewer_first_read": "tram first",
            "desired_mood": "natural travel",
            "must_preserve": ["daylight realism"],
            "must_avoid": ["fake HDR"],
        },
        "control_selections": [
            {
                "control_id": "Exposure.Curve",
                "approved_value_id": "tone_curve.midtone_depth_v1",
                "reason": "approved depth curve",
                "expected_effect": "stronger separation",
                "risk": "hard sky",
                "risk_mitigation": "keep other controls moderate",
            },
            {
                "control_id": "Exposure.Compensation",
                "value": 0.2,
                "reason": "small lift",
                "expected_effect": "slightly brighter subject",
                "risk": "flat highlights",
                "risk_mitigation": "stay modest",
            },
            {
                "control_id": "Vibrance.Enabled",
                "value": True,
                "reason": "enable vibrance",
                "expected_effect": "color support",
                "risk": "oversaturation",
                "risk_mitigation": "keep values low",
            },
        ],
        "controls_considered_but_rejected": [
            {"control_id": "Local Contrast.Amount", "reason": "blocked by manifest"},
        ],
        "non_goals": ["do not create fake HDR"],
    }


class TestManifestSummary:
    def test_compact_manifest_summary_uses_agent_facing_fields_only(self):
        summary = build_agent_manifest_summary()
        assert "planning_contract" in summary
        controls = summary["controls"]
        assert isinstance(controls, list) and controls
        allowed_fields = {
            "control_id",
            "ui_name",
            "value_type",
            "allowed_range",
            "policy",
            "approved_values",
            "expected_effect",
            "risks",
            "confidence",
            "pending_evidence",
        }
        for entry in controls:
            assert set(entry).issubset(allowed_fields)

    def test_compact_manifest_summary_includes_ranges_approved_values_and_pending_evidence(self):
        summary = build_agent_manifest_summary()
        indexed = {entry["control_id"]: entry for entry in summary["controls"]}
        assert indexed["Exposure.Compensation"]["allowed_range"] == [-0.5, 0.8]
        assert indexed["Exposure.Curve"]["policy"] == "approved_curve_only"
        assert indexed["Exposure.Curve"]["approved_values"]
        assert indexed["Shadows & Highlights.Highlights"]["pending_evidence"] is True
        assert "pending_evidence_rule" in summary["planning_contract"]


class TestManifestSelectPlan:
    def test_llm_selected_allowed_controls_pass_validation(self):
        plan = build_manifest_select_edit_plan(_valid_edit_plan())
        assert plan["status"] == "ok"
        assert plan["validation"]["allowed"] is True
        assert "tone_curve" in plan["parameters"]

    def test_unknown_controls_are_blocked(self):
        payload = _valid_edit_plan()
        payload["control_selections"] = [
            {
                "control_id": "Retinex.Strength",
                "value": 10,
                "reason": "unknown",
                "expected_effect": "dehaze",
                "risk": "n/a",
                "risk_mitigation": "n/a",
            }
        ]
        plan = build_manifest_select_edit_plan(payload)
        assert plan["status"] == "control_selection_invalid"
        assert plan["blocked"][0]["control_id"] == "Retinex.Strength"

    def test_arbitrary_curves_are_blocked(self):
        payload = _valid_edit_plan()
        payload["control_selections"] = [
            {
                "control_id": "Exposure.Curve",
                "value": "3;0;0;0.5;0.5;1;1;",
                "reason": "custom curve",
                "expected_effect": "n/a",
                "risk": "n/a",
                "risk_mitigation": "n/a",
            }
        ]
        plan = build_manifest_select_edit_plan(payload)
        assert plan["status"] == "control_selection_invalid"
        assert "approved_value_id" in plan["blocked"][0]["reason"]

    def test_approved_exact_curves_pass(self):
        payload = _valid_edit_plan()
        payload["control_selections"] = [
            {
                "control_id": "Luminance Curve.lhCurve",
                "approved_value_id": "luminance_curve.landscape_depth_v1",
                "reason": "approved curve",
                "expected_effect": "depth",
                "risk": "hard haze",
                "risk_mitigation": "approved exact preset",
            }
        ]
        plan = build_manifest_select_edit_plan(payload)
        assert plan["status"] == "ok"
        assert "luminance_curve" in plan["parameters"]


class TestManifestSelectPrepare:
    async def test_prepare_reports_blocked_controls_without_silent_use(self, mock_ctx, tmp_path: Path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")
        payload = _valid_edit_plan()
        payload["control_selections"] = [
            {
                "control_id": "Local Contrast.Amount",
                "value": 10,
                "reason": "blocked",
                "expected_effect": "n/a",
                "risk": "n/a",
                "risk_mitigation": "n/a",
            }
        ]
        result = await auto_edit_manifest_select_prepare(mock_ctx, str(raw_file), payload)
        assert isinstance(result, dict)
        assert result["status"] == "control_selection_invalid"
        assert result["decision"] == "verification_required_not_reached"
        assert result["blocked"][0]["control_id"] == "Local Contrast.Amount"

    async def test_prepare_returns_verification_required_and_inline_images(self, mock_ctx, tmp_path: Path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (900, 600), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_manifest_select_prepare(mock_ctx, str(raw_file), _valid_edit_plan(), preview_width=800)

        assert isinstance(result, ToolResult)
        payload = result.structured_content
        assert payload is not None
        assert payload["decision"] == "verification_required"
        assert payload["prepare_mode"] == "manifest_select"
        assert payload["base_preview_path"]
        assert payload["edited_preview_path"]
        assert len(result.content) >= 3
        assert result.content[1].type == "image"

    async def test_verify_remains_only_final_decision_step(self, mock_ctx, tmp_path: Path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (900, 600), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            prepared = await auto_edit_manifest_select_prepare(mock_ctx, str(raw_file), _valid_edit_plan())
        prepare_payload = prepared.structured_content if isinstance(prepared, ToolResult) else prepared

        assert prepare_payload["decision"] == "verification_required"
        result = await verify_predictive_edit(
            mock_ctx,
            raw_path=str(raw_file),
            profile_path=prepare_payload["profile_path"],
            base_preview_path=prepare_payload["base_preview_path"],
            edited_preview_path=prepare_payload["edited_preview_path"],
            before_after_path=prepare_payload["before_after_path"],
            verification_observations={
                "subject_change_description": "Subject reads better.",
                "background_change_description": "Background is calmer.",
                "midtone_change_description": "Midtones improve.",
                "highlight_shadow_description": "Highlights remain believable.",
                "color_change_description": "Color improves naturally.",
                "artifact_description": "No obvious artifacts.",
                "crop_dependency_description": "Mostly tonal and not crop-driven.",
                "scores": {
                    "global_pixel_difference": 7.4,
                    "subject_separation_improvement": 7.3,
                    "non_crop_tonal_improvement": 7.2,
                    "color_intent_improvement": 7.1,
                    "highlight_shadow_quality": 6.9,
                    "composition_improvement": 4.0,
                    "crop_contribution": 2.0,
                    "perceived_non_crop_improvement": "moderate",
                    "artifact_check": "pass",
                    "naturalness_score": 8.0,
                    "artifact_free_score": 9.0,
                },
            },
            export=False,
        )
        payload = result.structured_content if isinstance(result, ToolResult) else result
        assert payload["decision_source"] == "verify_predictive_edit"
        assert payload["decision"] in {"proof_plus", "export"}

    async def test_deterministic_routing_remains_fallback_debug_only(self, mock_ctx, tmp_path: Path):
        raw_file = tmp_path / "photo.cr3"
        raw_file.write_bytes(b"raw")

        async def create_preview(**kwargs):
            out = kwargs["output_path"]
            PILImage.new("RGB", (900, 600), "gray").save(str(out), "JPEG")
            return {"success": True, "output_path": str(out), "processing_time": 0.3, "file_size": out.stat().st_size}

        with patch("rawtherapee_mcp.server.run_rt_cli", side_effect=create_preview):
            result = await auto_edit_predictive(mock_ctx, str(raw_file), export=False)

        assert result["fallback_only"] is True
        assert result["primary_prepare_tool"] == "auto_edit_manifest_select_prepare"
