# Predictive Editor Summary

## Phase 9.1 Result
- active_real_raw_entries: `3`
- run_folder: `docs/evaluations/runs_phase9/`
- prepare_decision_distribution: `verification_required=3`
- final_decision_distribution: `proof_plus=1`, `failed_edit_quality=1`, `proof_only=1`, `export=0`, `crop_only_improvement=0`
- decision_source_distribution: `verify_predictive_edit=3`
- inline_prepare_images: `3/3 reports include 3 attached images`
- inline_verify_images: `3/3 reports include 3 attached images`
- consistency_warning_count_real_runs: `0`
- synthetic_consistency_warning_case: `docs/evaluations/runs_phase9/synthetic_consistency_case/report.json`

## Protocol Checks
- Each real Phase 9 report now includes `Planner / Prepare Output`, `Rendered Preview Files`, `Inline Image Availability`, `Visual Verification Observations`, `Consistency Checks`, and `Final Decision`.
- Each real Phase 9 report records `decision_source = verify_predictive_edit`.
- `auto_edit_predictive_prepare` did not produce any final edit-quality decisions on the real set. All three returned `decision = verification_required`.
- `verify_predictive_edit` was the only final decision step on the real set.
- The synthetic contradiction case produced `4` consistency warnings without silently rewriting scores.

## Phase 8 vs Phase 9
### IMG_1279
- decision_before_phase9: `proof_plus`
- decision_after_phase9: `proof_plus`
- perceived_non_crop_improvement_before: `moderate`
- perceived_non_crop_improvement_after: `moderate`
- consistency_warnings: `0`
- notes: the enforced two-step flow preserved the prior outcome while moving final judgment to `verify_predictive_edit` and attaching base, edited, and before/after images in both steps.

### IMG_1850
- decision_before_phase9: `failed_edit_quality`
- decision_after_phase9: `failed_edit_quality`
- perceived_non_crop_improvement_before: `weak`
- perceived_non_crop_improvement_after: `weak`
- consistency_warnings: `0`
- notes: the protocol change did not inflate the landscape result; the edit remains honestly below meaningful non-crop quality and now records explicit prepare output plus verification observations.

### IMG_3709
- decision_before_phase9: `proof_only`
- decision_after_phase9: `proof_only`
- perceived_non_crop_improvement_before: `weak`
- perceived_non_crop_improvement_after: `weak`
- consistency_warnings: `0`
- notes: the low-light case stays modest under the new flow, with final classification still coming only from the verification step.

## Synthetic Consistency Case
- base_case: `IMG_1279` Phase 9 previews reused with contradictory descriptions and high artifact/naturalness/highlight-shadow scores
- result_decision_source: `verify_predictive_edit`
- warning_fields: `artifact_free_score`, `naturalness_score`, `highlight_shadow_quality`, `artifact_check`
- reading: warnings fired as expected when the text mentioned halos, fake HDR, harshness, clipping, cyan cast, and banding while the numeric scores still claimed a clean natural result.

## Interpretation
- Phase 9.1 validates the sequencing change without changing the real RAW outcomes.
- The important regression result is structural, not score-seeking: `prepare` now stops at rendered evidence, and `verify` owns the final decision in every real run.
- The report format now makes that separation visible and auditable.
