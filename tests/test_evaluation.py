"""Tests for predictive editor evaluation harness and CLI wrapper."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image as PILImage

from rawtherapee_mcp.evaluation import run_predictive_evaluation
from rawtherapee_mcp.predictive_editor import score_predictive_export_decision


def _load_cli_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "evaluate_predictive_editor.py"
    spec = importlib.util.spec_from_file_location("evaluate_predictive_editor_cli", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load evaluate_predictive_editor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_jpeg(path: Path, size: tuple[int, int] = (800, 600), color: str = "gray") -> None:
    PILImage.new("RGB", size, color).save(str(path), "JPEG")


class TestPredictiveEvaluation:
    def test_evaluation_creates_expected_report_and_artifacts(self, tmp_path: Path) -> None:
        raw_file = tmp_path / "IMG_1279.jpg"
        _write_jpeg(raw_file, color="white")

        source_base = tmp_path / "source_base.jpg"
        source_pred = tmp_path / "source_pred.jpg"
        source_profile = tmp_path / "source_profile.pp3"
        _write_jpeg(source_base, color="blue")
        _write_jpeg(source_pred, color="green")
        source_profile.write_text("[Version]\nAppVersion=5.11\n", encoding="utf-8")

        async def fake_preview_raw(*args, **kwargs):
            return {"success": True, "preview_path": str(source_base)}

        async def fake_auto_edit(*args, **kwargs):
            return {
                "decision": "preview_ready",
                "profile_path": str(source_profile),
                "preview_path": str(source_pred),
                "diagnosis": {"diagnosis": [{"issue": "dull_color_presence", "severity": 0.5, "evidence": "muted"}]},
                "parameters": {
                    "exposure": {"contrast": 10, "saturation": 4},
                    "vibrance": {"enabled": True, "pastels": 8, "saturated": 2},
                },
                "expected_effect": ["color presence should improve naturally"],
                "approved_curves_used": [
                    {
                        "id": "tone_curve.midtone_pop_v1",
                        "reason": "flat_midtone_geometry + weak_subject_readability",
                        "risk": "may increase harshness; checked by export gate",
                    }
                ],
                "validation": {"allowed": True, "blocked": [], "clamped": []},
                "blocked_controls_considered": [{"control": "Local Contrast.Amount", "reason": "blocked by manifest"}],
                "scores": {
                    "global_visible_difference_score": 7.8,
                    "global_pixel_difference": 7.8,
                    "subject_hierarchy_score": 7.4,
                    "thumbnail_subject_read_score": 7.2,
                    "color_quality_score": 7.5,
                    "naturalness_score": 8.0,
                    "artifact_free_score": 9.0,
                    "crop_dependency": "secondary",
                    "non_crop_tonal_improvement": 7.2,
                    "subject_separation_improvement": 7.4,
                    "color_intent_improvement": 7.3,
                    "highlight_shadow_quality": 6.6,
                    "composition_improvement": 5.0,
                    "crop_contribution": 3.0,
                    "perceived_non_crop_improvement": "moderate",
                    "export_gate_passed": True,
                },
            }

        async def fake_before_after(*args, **kwargs):
            return {"before": {"preview_path": str(source_base)}, "after": {"preview_path": str(source_pred)}}

        with (
            patch("rawtherapee_mcp.evaluation.preview_raw", side_effect=fake_preview_raw),
            patch("rawtherapee_mcp.evaluation.auto_edit_predictive", side_effect=fake_auto_edit),
            patch("rawtherapee_mcp.evaluation.preview_before_after", side_effect=fake_before_after),
        ):
            report = asyncio.run(
                run_predictive_evaluation(
                    raw_path=str(raw_file),
                    brief="warm natural travel",
                    intensity="medium",
                    output_root=tmp_path / "eval",
                )
            )

        assert "error" not in report
        files = report["files"]
        assert Path(files["base_preview"]).is_file()
        assert Path(files["predictive_preview"]).is_file()
        assert Path(files["before_after"]).is_file()
        assert Path(files["profile"]).is_file()
        assert Path(files["report_json"]).is_file()
        assert Path(files["report_md"]).is_file()

        parsed = json.loads(Path(files["report_json"]).read_text(encoding="utf-8"))
        assert parsed["source_type"] == "jpeg"
        assert parsed["is_raw_regression"] is False
        assert parsed["calibration_allowed"] is False
        assert "diagnosis" in parsed
        assert "parameters" in parsed
        assert "validation" in parsed
        assert "export_gate" in parsed
        assert parsed["approved_curves_used"][0]["id"] == "tone_curve.midtone_pop_v1"
        checks = parsed["failure_mode_checks"]
        assert checks["local_contrast_amount_emitted"] is False
        assert checks["hsv_hcurve_emitted"] is False
        assert checks["arbitrary_curves_emitted"] is False

    def test_jpeg_tiff_png_eval_reports_are_not_calibration_allowed(self, tmp_path: Path) -> None:
        source_base = tmp_path / "source_base.jpg"
        source_pred = tmp_path / "source_pred.jpg"
        source_profile = tmp_path / "source_profile.pp3"
        _write_jpeg(source_base, color="blue")
        _write_jpeg(source_pred, color="green")
        source_profile.write_text("[Version]\nAppVersion=5.11\n", encoding="utf-8")

        async def fake_preview_raw(*args, **kwargs):
            return {"success": True, "preview_path": str(source_base)}

        async def fake_auto_edit(*args, **kwargs):
            return {
                "decision": "proof_plus",
                "profile_path": str(source_profile),
                "preview_path": str(source_pred),
                "diagnosis": {"diagnosis": []},
                "parameters": {"exposure": {"contrast": 9}},
                "expected_effect": [],
                "validation": {"allowed": True, "blocked": [], "clamped": []},
                "blocked_controls_considered": [],
                "scores": {
                    "global_visible_difference_score": 7.0,
                    "global_pixel_difference": 7.0,
                    "subject_hierarchy_score": 6.0,
                    "thumbnail_subject_read_score": 6.0,
                    "color_quality_score": 7.0,
                    "naturalness_score": 8.0,
                    "artifact_free_score": 9.0,
                    "crop_dependency": "secondary",
                    "non_crop_tonal_improvement": 5.8,
                    "subject_separation_improvement": 5.7,
                    "color_intent_improvement": 5.9,
                    "highlight_shadow_quality": 5.2,
                    "composition_improvement": 4.0,
                    "crop_contribution": 2.0,
                    "perceived_non_crop_improvement": "weak",
                },
            }

        async def fake_before_after(*args, **kwargs):
            return {"before": {"preview_path": str(source_base)}, "after": {"preview_path": str(source_pred)}}

        cases = [("case.jpg", "jpeg"), ("case.tiff", "tiff"), ("case.png", "png")]
        with (
            patch("rawtherapee_mcp.evaluation.preview_raw", side_effect=fake_preview_raw),
            patch("rawtherapee_mcp.evaluation.auto_edit_predictive", side_effect=fake_auto_edit),
            patch("rawtherapee_mcp.evaluation.preview_before_after", side_effect=fake_before_after),
        ):
            for filename, expected_type in cases:
                source = tmp_path / filename
                PILImage.new("RGB", (100, 80), "white").save(source)
                report = asyncio.run(
                    run_predictive_evaluation(
                        raw_path=str(source),
                        brief="warm natural travel",
                        intensity="medium",
                        output_root=tmp_path / f"eval-{expected_type}",
                    )
                )
                assert report["source_type"] == expected_type
                assert report["is_raw_regression"] is False
                assert report["calibration_allowed"] is False

    def test_crop_only_decision_fails_export_gate(self, tmp_path: Path) -> None:
        raw_file = tmp_path / "crop_case.jpg"
        _write_jpeg(raw_file, color="white")

        source_base = tmp_path / "base.jpg"
        source_pred = tmp_path / "pred.jpg"
        source_profile = tmp_path / "pred.pp3"
        _write_jpeg(source_base, color="gray")
        _write_jpeg(source_pred, color="gray")
        source_profile.write_text("[Version]\nAppVersion=5.11\n", encoding="utf-8")

        async def fake_preview_raw(*args, **kwargs):
            return {"success": True, "preview_path": str(source_base)}

        async def fake_auto_edit(*args, **kwargs):
            return {
                "decision": "proof_only",
                "profile_path": str(source_profile),
                "preview_path": str(source_pred),
                "diagnosis": {"diagnosis": [{"issue": "proof_only_needed", "severity": 0.9, "evidence": "weak"}]},
                "parameters": {"crop": {"enabled": True, "ratio": "4:5"}},
                "expected_effect": ["proof-only direction"],
                "validation": {"allowed": True, "blocked": [], "clamped": []},
                "blocked_controls_considered": [],
                "scores": {
                    "global_visible_difference_score": 9.5,
                    "global_pixel_difference": 9.5,
                    "subject_hierarchy_score": 8.0,
                    "thumbnail_subject_read_score": 8.0,
                    "color_quality_score": 8.0,
                    "naturalness_score": 8.0,
                    "artifact_free_score": 9.0,
                    "crop_dependency": "primary",
                    "non_crop_tonal_improvement": 4.5,
                    "subject_separation_improvement": 4.8,
                    "color_intent_improvement": 4.2,
                    "highlight_shadow_quality": 4.0,
                    "composition_improvement": 8.2,
                    "crop_contribution": 8.9,
                    "perceived_non_crop_improvement": "weak",
                    "export_gate_passed": False,
                },
            }

        async def fake_before_after(*args, **kwargs):
            return {"before": {"preview_path": str(source_base)}, "after": {"preview_path": str(source_pred)}}

        with (
            patch("rawtherapee_mcp.evaluation.preview_raw", side_effect=fake_preview_raw),
            patch("rawtherapee_mcp.evaluation.auto_edit_predictive", side_effect=fake_auto_edit),
            patch("rawtherapee_mcp.evaluation.preview_before_after", side_effect=fake_before_after),
        ):
            report = asyncio.run(
                run_predictive_evaluation(
                    raw_path=str(raw_file),
                    brief="proof only",
                    intensity="medium",
                    output_root=tmp_path / "eval",
                )
            )

        assert report["export_gate"]["decision"] == "crop_only_improvement"
        assert report["export_gate"]["crop_dependency"] == "primary"
        assert report["export_gate"]["export_gate_passed"] is False

    def test_raw_eval_reports_are_calibration_allowed(self, tmp_path: Path) -> None:
        raw_file = tmp_path / "IMG_1279.CR3"
        raw_file.write_bytes(b"raw")

        source_base = tmp_path / "source_base.jpg"
        source_pred = tmp_path / "source_pred.jpg"
        source_profile = tmp_path / "source_profile.pp3"
        _write_jpeg(source_base, color="blue")
        _write_jpeg(source_pred, color="green")
        source_profile.write_text("[Version]\nAppVersion=5.11\n", encoding="utf-8")

        async def fake_preview_raw(*args, **kwargs):
            return {"success": True, "preview_path": str(source_base)}

        async def fake_auto_edit(*args, **kwargs):
            return {
                "decision": "failed_edit_quality",
                "profile_path": str(source_profile),
                "preview_path": str(source_pred),
                "diagnosis": {"diagnosis": []},
                "parameters": {"exposure": {"contrast": 9}},
                "expected_effect": [],
                "validation": {"allowed": True, "blocked": [], "clamped": []},
                "blocked_controls_considered": [],
                "scores": {
                    "global_visible_difference_score": 7.0,
                    "global_pixel_difference": 7.0,
                    "subject_hierarchy_score": 6.0,
                    "thumbnail_subject_read_score": 6.0,
                    "color_quality_score": 7.0,
                    "naturalness_score": 8.0,
                    "artifact_free_score": 9.0,
                    "crop_dependency": "secondary",
                    "non_crop_tonal_improvement": 5.8,
                    "subject_separation_improvement": 5.7,
                    "color_intent_improvement": 5.9,
                    "highlight_shadow_quality": 5.2,
                    "composition_improvement": 4.0,
                    "crop_contribution": 2.0,
                    "perceived_non_crop_improvement": "weak",
                },
            }

        async def fake_before_after(*args, **kwargs):
            return {"before": {"preview_path": str(source_base)}, "after": {"preview_path": str(source_pred)}}

        with (
            patch("rawtherapee_mcp.evaluation.preview_raw", side_effect=fake_preview_raw),
            patch("rawtherapee_mcp.evaluation.auto_edit_predictive", side_effect=fake_auto_edit),
            patch("rawtherapee_mcp.evaluation.preview_before_after", side_effect=fake_before_after),
        ):
            report = asyncio.run(
                run_predictive_evaluation(
                    raw_path=str(raw_file),
                    brief="warm natural travel",
                    intensity="medium",
                    output_root=tmp_path / "eval",
                )
            )

        assert report["source_type"] == "raw"
        assert report["is_raw_regression"] is True
        assert report["calibration_allowed"] is True
        assert report["export_gate"]["decision"] == "failed_edit_quality"

    def test_high_global_difference_cannot_pass_if_non_crop_tonal_improvement_is_weak(self) -> None:
        result = score_predictive_export_decision(
            validation_allowed=True,
            global_visible_difference_score=9.8,
            subject_hierarchy_score=6.0,
            thumbnail_subject_read_score=8.0,
            color_quality_score=8.0,
            naturalness_score=8.0,
            artifact_free_score=9.0,
            crop_dependency="secondary",
            global_pixel_difference=9.8,
            non_crop_tonal_improvement=5.0,
            subject_separation_improvement=6.2,
            color_intent_improvement=6.4,
            highlight_shadow_quality=5.4,
            composition_improvement=4.0,
            crop_contribution=2.0,
            perceived_non_crop_improvement="weak",
        )
        assert result["export_gate_passed"] is False
        assert result["decision"] == "failed_edit_quality"

    def test_proof_plus_requires_meaningful_non_crop_improvement(self) -> None:
        result = score_predictive_export_decision(
            validation_allowed=True,
            global_visible_difference_score=7.0,
            subject_hierarchy_score=6.0,
            thumbnail_subject_read_score=6.0,
            color_quality_score=7.0,
            naturalness_score=8.0,
            artifact_free_score=8.0,
            crop_dependency="none",
            global_pixel_difference=7.0,
            non_crop_tonal_improvement=7.2,
            subject_separation_improvement=7.1,
            color_intent_improvement=6.6,
            highlight_shadow_quality=5.8,
            composition_improvement=4.5,
            crop_contribution=2.0,
            perceived_non_crop_improvement="moderate",
        )
        assert result["export_gate_passed"] is False
        assert result["decision"] == "proof_plus"

    def test_img_1279_style_scores_now_fail_non_crop_quality(self) -> None:
        result = score_predictive_export_decision(
            validation_allowed=True,
            global_visible_difference_score=7.0,
            subject_hierarchy_score=6.0,
            thumbnail_subject_read_score=6.0,
            color_quality_score=7.0,
            naturalness_score=8.0,
            artifact_free_score=8.0,
            crop_dependency="secondary",
            global_pixel_difference=7.0,
            non_crop_tonal_improvement=6.1,
            subject_separation_improvement=6.2,
            color_intent_improvement=6.4,
            highlight_shadow_quality=5.7,
            composition_improvement=5.0,
            crop_contribution=3.0,
            perceived_non_crop_improvement="weak",
        )
        assert result["export_gate_passed"] is False
        assert result["decision"] == "failed_edit_quality"

    def test_crop_only_improvement_is_classified_separately(self) -> None:
        result = score_predictive_export_decision(
            validation_allowed=True,
            global_visible_difference_score=10.0,
            subject_hierarchy_score=9.0,
            thumbnail_subject_read_score=9.0,
            color_quality_score=9.0,
            naturalness_score=9.0,
            artifact_free_score=9.0,
            crop_dependency="primary",
            global_pixel_difference=10.0,
            non_crop_tonal_improvement=4.0,
            subject_separation_improvement=4.2,
            color_intent_improvement=4.0,
            highlight_shadow_quality=4.3,
            composition_improvement=8.5,
            crop_contribution=9.0,
            perceived_non_crop_improvement="weak",
        )
        assert result["export_gate_passed"] is False
        assert result["decision"] == "crop_only_improvement"

    def test_reports_include_non_crop_edit_quality_sentence(self, tmp_path: Path) -> None:
        raw_file = tmp_path / "IMG_1279.jpg"
        _write_jpeg(raw_file, color="white")

        source_base = tmp_path / "source_base.jpg"
        source_pred = tmp_path / "source_pred.jpg"
        source_profile = tmp_path / "source_profile.pp3"
        _write_jpeg(source_base, color="blue")
        _write_jpeg(source_pred, color="green")
        source_profile.write_text("[Version]\nAppVersion=5.11\n", encoding="utf-8")

        async def fake_preview_raw(*args, **kwargs):
            return {"success": True, "preview_path": str(source_base)}

        async def fake_auto_edit(*args, **kwargs):
            return {
                "decision": "failed_edit_quality",
                "profile_path": str(source_profile),
                "preview_path": str(source_pred),
                "diagnosis": {"diagnosis": []},
                "parameters": {"exposure": {"contrast": 9}},
                "expected_effect": [],
                "validation": {"allowed": True, "blocked": [], "clamped": []},
                "blocked_controls_considered": [],
                "scores": {
                    "global_visible_difference_score": 7.0,
                    "global_pixel_difference": 7.0,
                    "subject_hierarchy_score": 6.0,
                    "thumbnail_subject_read_score": 6.0,
                    "color_quality_score": 7.0,
                    "naturalness_score": 8.0,
                    "artifact_free_score": 9.0,
                    "crop_dependency": "secondary",
                    "non_crop_tonal_improvement": 5.8,
                    "subject_separation_improvement": 5.7,
                    "color_intent_improvement": 5.9,
                    "highlight_shadow_quality": 5.2,
                    "composition_improvement": 4.0,
                    "crop_contribution": 2.0,
                    "perceived_non_crop_improvement": "weak",
                },
            }

        async def fake_before_after(*args, **kwargs):
            return {"before": {"preview_path": str(source_base)}, "after": {"preview_path": str(source_pred)}}

        with (
            patch("rawtherapee_mcp.evaluation.preview_raw", side_effect=fake_preview_raw),
            patch("rawtherapee_mcp.evaluation.auto_edit_predictive", side_effect=fake_auto_edit),
            patch("rawtherapee_mcp.evaluation.preview_before_after", side_effect=fake_before_after),
        ):
            report = asyncio.run(
                run_predictive_evaluation(
                    raw_path=str(raw_file),
                    brief="warm natural travel",
                    intensity="medium",
                    output_root=tmp_path / "eval",
                )
            )

        markdown = Path(report["files"]["report_md"]).read_text(encoding="utf-8")
        assert "Non-crop edit quality: fail" in markdown
        assert "Reason:" in markdown

    def test_perceived_non_crop_improvement_is_included_in_report_parsing(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "scores.csv"
        raw_file = tmp_path / "IMG_1279.jpg"
        _write_jpeg(raw_file, color="white")
        csv_path.write_text(
            "image,brief,intensity,visible_difference,hierarchy_improvement,color_quality,naturalness,"
            "artifact_free,crop_dependency,perceived_non_crop_improvement,decision_correct,notes\n"
            'IMG_1279,"warm natural travel",medium,8,6.5,8,8,8,none,weak,yes,"weak base edit"\n',
            encoding="utf-8",
        )

        async def fake_preview_raw(*args, **kwargs):
            return {"success": True, "preview_path": str(tmp_path / "base.jpg")}

        async def fake_auto_edit(*args, **kwargs):
            return {
                "decision": "failed_edit_quality",
                "profile_path": str(tmp_path / "profile.pp3"),
                "preview_path": str(tmp_path / "pred.jpg"),
                "diagnosis": {"diagnosis": []},
                "parameters": {},
                "expected_effect": [],
                "validation": {"allowed": True, "blocked": [], "clamped": []},
                "blocked_controls_considered": [],
                "scores": {
                    "global_visible_difference_score": 7.0,
                    "global_pixel_difference": 7.0,
                    "subject_hierarchy_score": 6.0,
                    "thumbnail_subject_read_score": 6.0,
                    "color_quality_score": 7.0,
                    "naturalness_score": 8.0,
                    "artifact_free_score": 8.0,
                    "crop_dependency": "secondary",
                    "non_crop_tonal_improvement": 5.8,
                    "subject_separation_improvement": 5.7,
                    "color_intent_improvement": 5.9,
                    "highlight_shadow_quality": 5.2,
                    "composition_improvement": 4.0,
                    "crop_contribution": 2.0,
                    "perceived_non_crop_improvement": "weak",
                },
            }

        _write_jpeg(tmp_path / "base.jpg", color="blue")
        _write_jpeg(tmp_path / "pred.jpg", color="green")
        (tmp_path / "profile.pp3").write_text("[Version]\nAppVersion=5.11\n", encoding="utf-8")

        async def fake_before_after(*args, **kwargs):
            return {
                "before": {"preview_path": str(tmp_path / "base.jpg")},
                "after": {"preview_path": str(tmp_path / "pred.jpg")},
            }

        with (
            patch("rawtherapee_mcp.evaluation.SCORES_CSV", csv_path),
            patch("rawtherapee_mcp.evaluation.preview_raw", side_effect=fake_preview_raw),
            patch("rawtherapee_mcp.evaluation.auto_edit_predictive", side_effect=fake_auto_edit),
            patch("rawtherapee_mcp.evaluation.preview_before_after", side_effect=fake_before_after),
        ):
            report = asyncio.run(
                run_predictive_evaluation(
                    raw_path=str(raw_file),
                    brief="warm natural travel",
                    intensity="medium",
                    output_root=tmp_path / "eval-parse",
                )
            )

        human_scores = report["manual_score_comparison"]["human_scores"]
        assert human_scores["perceived_non_crop_improvement"] == "weak"

    def test_cli_script_exits_cleanly_with_mocked_runner(self, monkeypatch) -> None:
        module = _load_cli_module()

        async def fake_runner(**kwargs):
            return {"raw_path": kwargs["raw_path"], "files": {}}

        monkeypatch.setattr(module, "run_predictive_evaluation", fake_runner)
        monkeypatch.setattr(
            "sys.argv",
            [
                "evaluate_predictive_editor.py",
                "--raw",
                "fake.CR3",
                "--brief",
                "warm natural travel",
            ],
        )
        assert module.main() == 0
