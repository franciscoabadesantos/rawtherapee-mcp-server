# Predictive Editor Summary

## Phase 8 Result
- active_real_raw_entries: `3`
- proof_plus: `1`
- proof_only: `1`
- failed_edit_quality: `1`
- export: `0`
- crop_only_improvement: `0`
- average_subject_separation_improvement: `5.70`
- average_non_crop_tonal_improvement: `6.10`
- average_color_intent_improvement: `6.53`
- average_highlight_shadow_quality: `6.07`
- decision_accuracy_vs_human_scores: `1.00`

## Approved Tonal-Depth Presets
- `tone_curve.midtone_depth_v1`
- `luminance_curve.landscape_depth_v1`
- `luminance_curve.low_light_lift_v1`

## Before/After Delta vs Phase 7.1
### IMG_1279
- decision: `failed_edit_quality -> proof_plus`
- non_crop_tonal_improvement: `5.8 -> 7.0`
- subject_separation_improvement: `6.5 -> 7.2`
- highlight_shadow_quality: `6.0 -> 6.6`
- perceived_non_crop_improvement: `weak -> moderate`
- approved preset used: `tone_curve.midtone_depth_v1`
- reading: the stronger approved midtone-depth curve makes the tram read faster and gives the rails/background more layered depth before any crop.

### IMG_1850
- decision: `failed_edit_quality -> failed_edit_quality`
- non_crop_tonal_improvement: `5.2 -> 6.3`
- subject_separation_improvement: `5.0 -> 5.3`
- highlight_shadow_quality: `5.5 -> 6.6`
- perceived_non_crop_improvement: `weak -> weak`
- approved preset used: `luminance_curve.landscape_depth_v1`
- reading: cloud and hillside definition improve, but the haze and broad scene hierarchy still do not become meaningfully stronger.

### IMG_3709
- decision: `proof_only -> proof_only`
- non_crop_tonal_improvement: `4.0 -> 5.0`
- subject_separation_improvement: `4.2 -> 4.6`
- highlight_shadow_quality: `4.6 -> 5.0`
- perceived_non_crop_improvement: `none -> weak`
- approved preset used: `luminance_curve.low_light_lift_v1`
- reading: the subject becomes slightly easier to read, but the low-light gain remains modest and does not cross into meaningful non-crop improvement.

## Aggregate Interpretation
- The controlled tonal-depth family improved the system materially on the hierarchy-heavy street case.
- It also improved the two weaker cases numerically and visually, but not enough to satisfy the non-crop quality gate.
- This means the added family is useful: it produced the first real `proof_plus` result without harming `naturalness_score` or `artifact_free_score`.
- The remaining limitation is breadth and scene specificity. Midtone-depth shaping helps urban geometry more than haze-heavy landscapes or dim single-subject dusk scenes.

## Recommendation
- Keep the current Phase 8 tonal-depth family.
- Next capability work should focus on one additional controlled family aimed at haze / sky structure or low-light subject lift, because those are the two remaining failure patterns on the real RAW set.
- Do not relax the honesty gate. The Phase 8 result is promising specifically because only one image crossed into `proof_plus`, while the other two remained honestly classified.
