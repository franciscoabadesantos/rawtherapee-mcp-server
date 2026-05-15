"""Evaluation harness for predictive autonomous editing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fastmcp import Context
from fastmcp.tools import ToolResult
from PIL import Image as PILImage

from rawtherapee_mcp.config import RTConfig, load_config
from rawtherapee_mcp.server import auto_edit_predictive, preview_before_after, preview_raw


@dataclass
class _EvalContext:
    """Minimal context adapter for tool functions outside MCP runtime."""

    lifespan_context: dict[str, Any]


def _structured_payload(result: dict[str, Any] | ToolResult) -> dict[str, Any]:
    if isinstance(result, ToolResult):
        payload = result.structured_content
        if isinstance(payload, dict):
            return payload
        return {}
    return result


def _copy_existing(src: str | None, dst: Path) -> str | None:
    if not src:
        return None
    path = Path(src)
    if not path.is_file():
        return None
    dst.write_bytes(path.read_bytes())
    return str(dst)


def _build_before_after(before_path: str | None, after_path: str | None, out_path: Path) -> str | None:
    if not before_path or not after_path:
        return None
    before = Path(before_path)
    after = Path(after_path)
    if not before.is_file() or not after.is_file():
        return None

    with PILImage.open(before) as before_img, PILImage.open(after) as after_img:
        height = max(before_img.height, after_img.height)
        width = before_img.width + after_img.width
        canvas = PILImage.new("RGB", (width, height), color="black")
        canvas.paste(before_img.convert("RGB"), (0, 0))
        canvas.paste(after_img.convert("RGB"), (before_img.width, 0))
        canvas.save(out_path, "JPEG")
    return str(out_path)


def _contains_banned_controls(parameters: dict[str, Any]) -> dict[str, bool]:
    local_contrast_used = "local_contrast" in parameters
    hsv_group = parameters.get("hsv_equalizer", {})
    hsv_hcurve_used = isinstance(hsv_group, dict) and "h_curve" in hsv_group
    arbitrary_curves_used = any(key in parameters for key in ("tone_curve", "rgb_curves"))
    return {
        "local_contrast_amount_emitted": local_contrast_used,
        "hsv_hcurve_emitted": hsv_hcurve_used,
        "arbitrary_curves_emitted": arbitrary_curves_used,
    }


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Predictive Editor Evaluation")
    lines.append("")
    lines.append(f"- raw_path: `{report['raw_path']}`")
    lines.append(f"- brief: `{report['brief']}`")
    lines.append(f"- intensity: `{report['intensity']}`")
    lines.append(f"- style: `{report['style']}`")
    lines.append("")
    lines.append("## Diagnosis")
    for item in report.get("diagnosis", []):
        if isinstance(item, dict):
            lines.append(f"- {item.get('issue')} (severity={item.get('severity')}): {item.get('evidence')}")
    lines.append("")
    lines.append("## Parameters")
    lines.append("```json")
    lines.append(json.dumps(report.get("parameters", {}), indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Expected Effects")
    for effect in report.get("expected_effect", []):
        lines.append(f"- {effect}")
    lines.append("")
    lines.append("## Validation")
    lines.append("```json")
    lines.append(json.dumps(report.get("validation", {}), indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Export Gate")
    lines.append("```json")
    lines.append(json.dumps(report.get("export_gate", {}), indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Preview Files")
    files = report.get("files", {})
    if isinstance(files, dict):
        for key in ("base_preview", "predictive_preview", "before_after", "profile"):
            lines.append(f"- {key}: `{files.get(key)}`")
    lines.append("")
    lines.append("## Visual Inspection Checklist")
    lines.append("- Subject readability improved")
    lines.append("- Thumbnail impact improved")
    lines.append("- Sky/highlights remain believable")
    lines.append("- No local-contrast crunch")
    lines.append("- Not crop-only")
    return "\n".join(lines) + "\n"


async def run_predictive_evaluation(
    *,
    raw_path: str,
    brief: str,
    intensity: str = "medium",
    style: str | None = None,
    preview_width: int = 1024,
    export: bool = False,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Run predictive-edit evaluation and write file artifacts + reports."""
    source = Path(raw_path)
    if not source.is_file():
        return {"error": f"File not found: {raw_path}"}

    config: RTConfig = load_config()
    ctx = cast(Context, _EvalContext(lifespan_context={"config": config}))
    resolved_output_root = output_root or (Path("docs") / "evaluations" / "runs")

    run_dir = resolved_output_root / source.stem
    run_dir.mkdir(parents=True, exist_ok=True)

    base_preview_result = await preview_raw(
        ctx, str(source), profile_path=None, max_width=preview_width, return_image=False
    )
    base_payload = _structured_payload(base_preview_result)
    if "error" in base_payload:
        return {"error": "Failed to generate base preview", "details": base_payload}

    base_preview_out = run_dir / "base_preview.jpg"
    base_preview_path = _copy_existing(base_payload.get("preview_path"), base_preview_out)

    predictive_result = await auto_edit_predictive(
        ctx,
        raw_path=str(source),
        style=style or brief,
        intensity=intensity,
        user_brief=brief,
        export=export,
        preview_width=preview_width,
    )
    if "error" in predictive_result:
        return {"error": "auto_edit_predictive failed", "details": predictive_result}

    profile_out = run_dir / "predictive_profile.pp3"
    profile_path = _copy_existing(predictive_result.get("profile_path"), profile_out)

    predictive_preview_out = run_dir / "predictive_preview.jpg"
    predictive_preview_path = _copy_existing(predictive_result.get("preview_path"), predictive_preview_out)

    before_after_result = {}
    before_after_out_path: str | None = None
    if profile_path:
        before_after_result = _structured_payload(
            await preview_before_after(ctx, str(source), profile_path, max_width=preview_width)
        )
        before_path = None
        after_path = None
        if isinstance(before_after_result.get("before"), dict):
            before_path = before_after_result["before"].get("preview_path")
        if isinstance(before_after_result.get("after"), dict):
            after_path = before_after_result["after"].get("preview_path")
        before_after_out_path = _build_before_after(before_path, after_path, run_dir / "before_after.jpg")

    parameters = predictive_result.get("parameters", {})
    if not isinstance(parameters, dict):
        parameters = {}
    scores = predictive_result.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}
    validation = predictive_result.get("validation", {})
    if not isinstance(validation, dict):
        validation = {}

    banned_checks = _contains_banned_controls(parameters)
    export_gate_passed = bool(scores.get("export_gate_passed", False))
    export_gate = {
        "visible_difference_score": scores.get("visible_difference_score", 0),
        "hierarchy_improvement_score": scores.get("hierarchy_improvement_score", 0),
        "artifact_check": scores.get("artifact_check", "unknown"),
        "crop_dependency": scores.get("crop_dependency", "unknown"),
        "decision": "export" if export_gate_passed else "proof_only",
        "export_gate_passed": export_gate_passed,
        "export_requested": export,
        "runtime_decision": predictive_result.get("decision"),
    }

    report: dict[str, Any] = {
        "raw_path": str(source),
        "brief": brief,
        "intensity": intensity,
        "style": style or brief,
        "diagnosis": predictive_result.get("diagnosis", {}).get("diagnosis", []),
        "parameters": parameters,
        "expected_effect": predictive_result.get("expected_effect", []),
        "validation": validation,
        "blocked_controls_considered": predictive_result.get("blocked_controls_considered", []),
        "export_gate": export_gate,
        "failure_mode_checks": banned_checks,
        "files": {
            "base_preview": base_preview_path,
            "predictive_preview": predictive_preview_path,
            "before_after": before_after_out_path,
            "profile": profile_path,
            "report_json": str(run_dir / "report.json"),
            "report_md": str(run_dir / "report.md"),
        },
    }

    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(_render_markdown_report(report), encoding="utf-8")

    return report
