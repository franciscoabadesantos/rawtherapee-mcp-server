"""Tests for predictive editor evaluation harness and CLI wrapper."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image as PILImage

from rawtherapee_mcp.evaluation import run_predictive_evaluation


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
                "validation": {"allowed": True, "blocked": [], "clamped": []},
                "blocked_controls_considered": [{"control": "Local Contrast.Amount", "reason": "blocked by manifest"}],
                "scores": {
                    "visible_difference_score": 7.8,
                    "hierarchy_improvement_score": 7.4,
                    "artifact_check": "pass",
                    "crop_dependency": "secondary",
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
        assert "diagnosis" in parsed
        assert "parameters" in parsed
        assert "validation" in parsed
        assert "export_gate" in parsed
        checks = parsed["failure_mode_checks"]
        assert checks["local_contrast_amount_emitted"] is False
        assert checks["hsv_hcurve_emitted"] is False
        assert checks["arbitrary_curves_emitted"] is False

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
                    "visible_difference_score": 5.5,
                    "hierarchy_improvement_score": 5.0,
                    "artifact_check": "pass",
                    "crop_dependency": "primary",
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

        assert report["export_gate"]["decision"] == "proof_only"
        assert report["export_gate"]["crop_dependency"] == "primary"
        assert report["export_gate"]["export_gate_passed"] is False

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
