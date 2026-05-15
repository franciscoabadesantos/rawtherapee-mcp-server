"""Evaluation harness for predictive autonomous editing."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fastmcp import Context
from fastmcp.tools import ToolResult
from PIL import Image as PILImage

from rawtherapee_mcp.config import RTConfig, load_config
from rawtherapee_mcp.control_policy import find_approved_curve
from rawtherapee_mcp.predictive_editor import score_predictive_export_decision
from rawtherapee_mcp.server import auto_edit_predictive, preview_before_after, preview_raw

RAW_SUFFIXES = {
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".arw",
    ".srf",
    ".sr2",
    ".raf",
    ".orf",
    ".rw2",
    ".rwl",
    ".dng",
    ".pef",
    ".ptx",
    ".3fr",
    ".fff",
    ".iiq",
    ".mrw",
    ".mef",
    ".mos",
    ".kdc",
    ".dcr",
    ".raw",
    ".srw",
    ".x3f",
    ".erf",
}
IMAGE_SUFFIX_TO_SOURCE_TYPE = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".png": "png",
}
SCORES_CSV = Path("docs") / "evaluations" / "predictive_editor_scores.csv"


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
    tone_curve_group = parameters.get("tone_curve", {})
    approved_tone_curve = (
        isinstance(tone_curve_group, dict)
        and find_approved_curve("Exposure", "Curve", tone_curve_group.get("curve")) is not None
    )
    luminance_curve_group = parameters.get("luminance_curve", {})
    approved_lh_curve = isinstance(luminance_curve_group, dict) and (
        "lh_curve" not in luminance_curve_group
        or find_approved_curve("Luminance Curve", "lhCurve", luminance_curve_group.get("lh_curve")) is not None
    )
    approved_hh_curve = isinstance(luminance_curve_group, dict) and (
        "hh_curve" not in luminance_curve_group
        or find_approved_curve("Luminance Curve", "hhCurve", luminance_curve_group.get("hh_curve")) is not None
    )
    arbitrary_curves_used = "rgb_curves" in parameters or (
        "tone_curve" in parameters and not approved_tone_curve
    ) or (
        "luminance_curve" in parameters and (not approved_lh_curve or not approved_hh_curve)
    )
    return {
        "local_contrast_amount_emitted": local_contrast_used,
        "hsv_hcurve_emitted": hsv_hcurve_used,
        "arbitrary_curves_emitted": arbitrary_curves_used,
    }


def _source_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in RAW_SUFFIXES:
        return "raw"
    return IMAGE_SUFFIX_TO_SOURCE_TYPE.get(suffix, "unknown")


def _decision_from_scores(scores: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    validation_allowed = bool(validation.get("allowed", False))
    global_visible = float(scores.get("global_visible_difference_score", scores.get("visible_difference_score", 0)))
    global_pixel_difference = float(scores.get("global_pixel_difference", global_visible))
    subject_hierarchy = float(scores.get("subject_hierarchy_score", scores.get("hierarchy_improvement_score", 0)))
    thumbnail_read = float(scores.get("thumbnail_subject_read_score", scores.get("hierarchy_improvement_score", 0)))
    color_quality = float(scores.get("color_quality_score", 0))
    naturalness = float(scores.get("naturalness_score", 0))
    artifact_free = float(scores.get("artifact_free_score", 9 if scores.get("artifact_check") == "pass" else 0))
    crop_dependency = str(scores.get("crop_dependency", "unknown"))
    decision = score_predictive_export_decision(
        validation_allowed=validation_allowed,
        global_visible_difference_score=global_visible,
        subject_hierarchy_score=subject_hierarchy,
        thumbnail_subject_read_score=thumbnail_read,
        color_quality_score=color_quality,
        naturalness_score=naturalness,
        artifact_free_score=artifact_free,
        crop_dependency=crop_dependency,
        global_pixel_difference=global_pixel_difference,
        non_crop_tonal_improvement=float(scores.get("non_crop_tonal_improvement", 0.0)),
        subject_separation_improvement=float(scores.get("subject_separation_improvement", 0.0)),
        color_intent_improvement=float(scores.get("color_intent_improvement", 0.0)),
        highlight_shadow_quality=float(scores.get("highlight_shadow_quality", 0.0)),
        composition_improvement=float(scores.get("composition_improvement", 0.0)),
        crop_contribution=float(scores.get("crop_contribution", 0.0)),
        perceived_non_crop_improvement=(
            str(scores["perceived_non_crop_improvement"])
            if "perceived_non_crop_improvement" in scores
            else None
        ),
    )
    return {
        "global_visible_difference_score": global_visible,
        "global_pixel_difference": global_pixel_difference,
        "subject_hierarchy_score": subject_hierarchy,
        "thumbnail_subject_read_score": thumbnail_read,
        "color_quality_score": color_quality,
        "naturalness_score": naturalness,
        "artifact_free_score": artifact_free,
        "artifact_check": "pass" if artifact_free >= 8.0 else "fail",
        "crop_dependency": crop_dependency,
        "non_crop_tonal_improvement": float(scores.get("non_crop_tonal_improvement", 0.0)),
        "subject_separation_improvement": float(scores.get("subject_separation_improvement", 0.0)),
        "color_intent_improvement": float(scores.get("color_intent_improvement", 0.0)),
        "highlight_shadow_quality": float(scores.get("highlight_shadow_quality", 0.0)),
        "composition_improvement": float(scores.get("composition_improvement", 0.0)),
        "crop_contribution": float(scores.get("crop_contribution", 0.0)),
        "perceived_non_crop_improvement": decision["perceived_non_crop_improvement"],
        "meaningful_non_crop_edit": decision["meaningful_non_crop_edit"],
        "non_crop_quality_pass_count": decision["non_crop_quality_pass_count"],
        "non_crop_quality_pass_fields": decision["non_crop_quality_pass_fields"],
        "crop_only_improvement": decision["crop_only_improvement"],
        "non_crop_edit_quality": decision["non_crop_edit_quality"],
        "non_crop_edit_quality_reason": decision["non_crop_edit_quality_reason"],
        "hierarchy_boost_applied": bool(scores.get("hierarchy_boost_applied", False)),
        "decision": decision["decision"],
        "export_gate_passed": decision["export_gate_passed"],
        "gate_requirements": decision["gate_requirements"],
        "scoring_guidance": decision["scoring_guidance"],
        "visible_difference_score": global_visible,
        "hierarchy_improvement_score": subject_hierarchy,
    }


def _human_score_to_visual_verification(human_scores: dict[str, Any] | None) -> dict[str, Any] | None:
    if human_scores is None:
        return None

    def _num(key: str, default: float) -> float:
        value = human_scores.get(key, default)
        return float(value) if isinstance(value, (int, float)) else default

    crop_dependency = str(human_scores.get("crop_dependency", "secondary"))
    crop_contribution = _num(
        "crop_contribution",
        8.0 if crop_dependency == "primary" else (2.0 if crop_dependency == "none" else 5.0),
    )
    subject_separation = _num("subject_separation_improvement", _num("hierarchy_improvement", 0.0))
    return {
        "subject": "primary subject",
        "before_after_judgment": {
            "global_pixel_difference": _num("global_pixel_difference", _num("visible_difference", 0.0)),
            "non_crop_tonal_improvement": _num(
                "non_crop_tonal_improvement",
                max(0.0, subject_separation - 0.7),
            ),
            "subject_separation_improvement": subject_separation,
            "color_intent_improvement": _num("color_intent_improvement", _num("color_quality", 0.0)),
            "highlight_shadow_quality": _num("highlight_shadow_quality", min(_num("naturalness", 0.0), 6.0)),
            "composition_improvement": _num(
                "composition_improvement",
                4.0 if crop_dependency == "none" else (8.0 if crop_dependency == "primary" else 5.5),
            ),
            "crop_contribution": crop_contribution,
            "perceived_non_crop_improvement": str(human_scores.get("perceived_non_crop_improvement", "weak")),
            "artifact_check": "pass" if _num("artifact_free", 0.0) >= 8.0 else "fail",
            "artifact_free_score": _num("artifact_free", 0.0),
            "naturalness_score": _num("naturalness", 0.0),
            "subject_hierarchy_score": subject_separation,
            "thumbnail_subject_read_score": _num("thumbnail_subject_read_score", subject_separation),
            "color_quality_score": _num("color_quality", 0.0),
            "reason": str(human_scores.get("notes", "Human visual verification row.")),
        },
    }


def _maybe_number(value: str) -> float | str:
    try:
        return float(value)
    except ValueError:
        return value


def _load_human_score(
    source: Path,
    brief: str,
    intensity: str,
    scores_csv: Path | None = None,
) -> dict[str, Any] | None:
    resolved_scores_csv = scores_csv or SCORES_CSV
    if not resolved_scores_csv.is_file():
        return None
    with resolved_scores_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row:
                continue
            image_matches = row.get("image") in {source.stem, source.name}
            brief_matches = not row.get("brief") or row.get("brief") == brief
            intensity_matches = not row.get("intensity") or row.get("intensity") == intensity
            if image_matches and brief_matches and intensity_matches:
                return {key: _maybe_number(value) for key, value in row.items() if value != ""}
    return None


def _manual_score_comparison(
    *,
    source: Path,
    brief: str,
    intensity: str,
    automated_scores: dict[str, Any],
) -> dict[str, Any] | None:
    human_scores = _load_human_score(source, brief, intensity)
    if human_scores is None:
        return None
    score_delta: dict[str, Any] = {}
    mapping = {
        "visible_difference": "global_visible_difference_score",
        "hierarchy_improvement": "subject_hierarchy_score",
        "color_quality": "color_quality_score",
        "naturalness": "naturalness_score",
        "artifact_free": "artifact_free_score",
        "non_crop_tonal_improvement": "non_crop_tonal_improvement",
        "subject_separation_improvement": "subject_separation_improvement",
        "color_intent_improvement": "color_intent_improvement",
        "highlight_shadow_quality": "highlight_shadow_quality",
        "composition_improvement": "composition_improvement",
        "crop_contribution": "crop_contribution",
    }
    for human_key, auto_key in mapping.items():
        human_value = human_scores.get(human_key)
        auto_value = automated_scores.get(auto_key)
        if isinstance(human_value, (int, float)) and isinstance(auto_value, (int, float)):
            score_delta[human_key] = f"{auto_value - human_value:+.1f}"
    if "decision_correct" in human_scores:
        score_delta["decision_correct"] = human_scores["decision_correct"]
    return {
        "automated_scores": automated_scores,
        "human_scores": human_scores,
        "score_delta": score_delta,
    }


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Predictive Editor Evaluation")
    lines.append("")
    lines.append(f"- raw_path: `{report['raw_path']}`")
    lines.append(f"- source_type: `{report['source_type']}`")
    lines.append(f"- is_raw_regression: `{report['is_raw_regression']}`")
    lines.append(f"- calibration_allowed: `{report['calibration_allowed']}`")
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
    lines.append("## Planner Expected")
    planned_scores = report.get("planned_scores", {})
    if isinstance(planned_scores, dict):
        lines.append("```json")
        lines.append(json.dumps(planned_scores, indent=2))
        lines.append("```")
        lines.append("")
    lines.append("## Expected Effects")
    for effect in report.get("expected_effect", []):
        lines.append(f"- {effect}")
    approved_curves = report.get("approved_curves_used", [])
    if isinstance(approved_curves, list) and approved_curves:
        lines.append("")
        lines.append("## Approved Curves")
        lines.append("```json")
        lines.append(json.dumps(approved_curves, indent=2))
        lines.append("```")
    lines.append("")
    lines.append("## Validation")
    lines.append("```json")
    lines.append(json.dumps(report.get("validation", {}), indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## Visual Verification Observed")
    lines.append("```json")
    lines.append(json.dumps(report.get("visual_verification_scores", {}), indent=2))
    lines.append("```")
    lines.append(f"- Decision source: {report.get('decision_source', 'visual_verification_pending')}")
    non_crop_quality = report.get("visual_verification_scores", {})
    if isinstance(non_crop_quality, dict):
        lines.append("")
        lines.append(
            f"Non-crop edit quality: {non_crop_quality.get('non_crop_edit_quality', 'fail')}"
        )
        lines.append(f"Reason: {non_crop_quality.get('non_crop_edit_quality_reason', 'Unavailable.')}")
    lines.append("")
    lines.append("## Export Gate")
    lines.append("```json")
    lines.append(json.dumps(report.get("export_gate", {}), indent=2))
    lines.append("```")
    comparison = report.get("manual_score_comparison")
    if isinstance(comparison, dict):
        lines.append("")
        lines.append("## Manual Score Comparison")
        lines.append("```json")
        lines.append(json.dumps(comparison, indent=2))
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

    human_scores = _load_human_score(source, brief, intensity)
    visual_verification_feedback = _human_score_to_visual_verification(human_scores)

    predictive_result = await auto_edit_predictive(
        ctx,
        raw_path=str(source),
        style=style or brief,
        intensity=intensity,
        user_brief=brief,
        export=export,
        preview_width=preview_width,
        verification_feedback=visual_verification_feedback,
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
    planned_scores = predictive_result.get("planned_scores", {})
    if not isinstance(planned_scores, dict):
        planned_scores = {}
    scores = predictive_result.get("visual_verification_scores", predictive_result.get("scores", {}))
    if not isinstance(scores, dict):
        scores = {}
    validation = predictive_result.get("validation", {})
    if not isinstance(validation, dict):
        validation = {}

    banned_checks = _contains_banned_controls(parameters)
    source_type = _source_type(source)
    is_raw_regression = source_type == "raw"
    calibration_allowed = is_raw_regression
    export_gate = _decision_from_scores(scores, validation)
    export_gate["export_requested"] = export
    export_gate["runtime_decision"] = predictive_result.get("decision")
    export_gate["decision_source"] = predictive_result.get("decision_source", "visual_verification_pending")
    manual_score_comparison = _manual_score_comparison(
        source=source,
        brief=brief,
        intensity=intensity,
        automated_scores=export_gate,
    )

    report: dict[str, Any] = {
        "raw_path": str(source),
        "source_path": str(source),
        "source_type": source_type,
        "is_raw_regression": is_raw_regression,
        "calibration_allowed": calibration_allowed,
        "brief": brief,
        "intensity": intensity,
        "style": style or brief,
        "diagnosis": predictive_result.get("diagnosis", {}).get("diagnosis", []),
        "parameters": parameters,
        "expected_effect": predictive_result.get("expected_effect", []),
        "planned_scores": planned_scores,
        "visual_verification_scores": scores,
        "decision_source": predictive_result.get("decision_source", "visual_verification_pending"),
        "approved_curves_used": predictive_result.get("approved_curves_used", []),
        "validation": validation,
        "blocked_controls_considered": predictive_result.get("blocked_controls_considered", []),
        "export_gate": export_gate,
        "manual_score_comparison": manual_score_comparison,
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
