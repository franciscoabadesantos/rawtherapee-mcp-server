# Predictive Editor Summary

## Phase 10 Result
- run_folder: `docs/evaluations/runs_phase10/`
- active_real_raw_entries: `3`
- prepare_mode: `manifest_select`
- prepare_decision_distribution: `verification_required=3`
- final_decision_distribution: `proof_plus=1`, `failed_edit_quality=1`, `proof_only=1`, `export=0`, `crop_only_improvement=0`
- decision_source_distribution: `verify_predictive_edit=3`
- inline_prepare_images: `3/3 reports include 3 attached images`
- inline_verify_images: `3/3 reports include 3 attached images`
- validation_failures_real_runs: `0`
- regression_summary_json: `docs/evaluations/runs_phase10/phase10_regression_summary.json`

## Protocol Checks
- `auto_edit_manifest_select_prepare` never returned `proof_plus`, `failed_edit_quality`, `proof_only`, or `export` on the real set. All three reports show `prepare_output.decision = verification_required`.
- `verify_predictive_edit` remained the only final decision step on all three real runs.
- Each real Phase 10 report includes `Planner / Prepare Output`, `Rendered Preview Files`, `Inline Image Availability`, `Visual Verification Observations`, `Consistency Checks`, and `Final Decision`.
- The synthetic contradiction case from Phase 9 remains the reference for warning behavior, and the Phase 10 path reuses the same `verify_predictive_edit` warning logic unchanged.

## Phase 9 Deterministic Routing vs Phase 10 Manifest-Select
### IMG_1279
- decision: `proof_plus -> proof_plus`
- perceived_non_crop_improvement: `moderate -> moderate`
- subject_separation_improvement: `7.2 -> 7.1`
- non_crop_tonal_improvement: `7.0 -> 6.9`
- color_intent_improvement: `8.1 -> 7.8`
- highlight_shadow_quality: `6.6 -> 6.5`
- naturalness_score: `8.0 -> 8.0`
- artifact_free_score: `8.0 -> 8.0`
- controls_selected: `Exposure.Curve[tone_curve.midtone_depth_v1]`, `Exposure.Compensation`, `Exposure.Contrast`, `Luminance Curve.Enabled`, `Luminance Curve.Contrast`, `Luminance Curve.AvoidColorShift`, `SharpenMicro.Enabled`, `SharpenMicro.Amount`, `Vibrance.Enabled`, `Vibrance.Pastels`, `Vibrance.Saturated`, `Vibrance.ProtectSkins`, `Vibrance.AvoidColorShift`
- controls_rejected: `Local Contrast.Amount`, `HSV Equalizer.HCurve`
- validation_failures: `none`
- reading: the manifest-select path independently chose a very similar safe stack to the deterministic proof-plus case, which is a good sign that the manifest + vision framing is coherent on the strongest image.

### IMG_1850
- decision: `failed_edit_quality -> failed_edit_quality`
- perceived_non_crop_improvement: `weak -> weak`
- subject_separation_improvement: `5.3 -> 5.2`
- non_crop_tonal_improvement: `6.3 -> 6.0`
- color_intent_improvement: `6.4 -> 6.3`
- highlight_shadow_quality: `6.6 -> 6.4`
- naturalness_score: `8.5 -> 8.4`
- artifact_free_score: `9.0 -> 9.0`
- controls_selected: `Luminance Curve.lhCurve[luminance_curve.landscape_depth_v1]`, `Exposure.HighlightCompr`, `Exposure.HighlightComprThreshold`, `Exposure.Contrast`, `Vibrance.Enabled`, `Vibrance.Pastels`, `Vibrance.Saturated`, `Vibrance.AvoidColorShift`
- controls_rejected: `Retinex`, `Local Contrast.Amount`, `HSV Equalizer.HCurve`
- validation_failures: `none`
- reading: this is the clearest capability-ceiling signal. The LLM-selected path correctly asked for a haze-specific family it could not use, then stayed inside the manifest and still landed on an honestly weak result.

### IMG_3709
- decision: `proof_only -> proof_only`
- perceived_non_crop_improvement: `weak -> weak`
- subject_separation_improvement: `4.6 -> 4.5`
- non_crop_tonal_improvement: `5.0 -> 4.9`
- color_intent_improvement: `5.1 -> 5.0`
- highlight_shadow_quality: `5.0 -> 5.1`
- naturalness_score: `8.3 -> 8.3`
- artifact_free_score: `9.0 -> 9.0`
- controls_selected: `Luminance Curve.lhCurve[luminance_curve.low_light_lift_v1]`, `Exposure.Compensation`, `Exposure.Saturation`, `Vibrance.Enabled`, `Vibrance.Pastels`, `Vibrance.Saturated`
- controls_rejected: `Shadows & Highlights.Shadows`, `Local Contrast.Amount`, `Retinex`
- validation_failures: `none`
- reading: the manifest-select path stayed cautious around pending-evidence shadow recovery and noise risk, which kept the result honest but also confirmed the limited ceiling of the current low-light toolkit.

## Interpretation
- Phase 10 successfully changes who chooses the controls without weakening any of the existing safety or verification guarantees.
- The strongest evidence is not that scores improved; it is that the system can now produce image-specific, vision-grounded control proposals, record capability ceilings explicitly, and still end at the same honest verification gate.
- `IMG_1850` is the most useful signal for future capability work. The manifest-select planner correctly identified the missing haze/dehaze family instead of pretending the current control set could fully solve the image.
