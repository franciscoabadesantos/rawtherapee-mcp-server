# Predictive Editor Evaluation

- raw_path: `/mnt/c/Users/santo/Pictures/IMG_1279.CR3`
- source_type: `raw`
- is_raw_regression: `True`
- calibration_allowed: `True`
- brief: `warm natural travel edit; improve subject separation and color presence without fake HDR`
- intensity: `medium`
- style: `warm natural travel edit; improve subject separation and color presence without fake HDR`

## Diagnosis
- flat_midtone_geometry (severity=0.65): Urban/travel framing often needs stronger midtone separation.
- weak_subject_readability (severity=0.55): Primary subject likely competes with structural background.
- low_thumbnail_impact (severity=0.55): Travel/street scenes often lose hierarchy at thumbnail size.
- dull_color_presence (severity=0.45): Brief/style requests stronger but natural color presence.

## Parameters
```json
{
  "tone_curve": {
    "curve_mode": "Standard",
    "curve": "3;0;0;0.45;0.52;1;1;",
    "curve2": "0;"
  },
  "exposure": {
    "contrast": 12,
    "compensation": 0.358,
    "saturation": 4
  },
  "luminance_curve": {
    "enabled": true,
    "contrast": 8,
    "avoid_color_shift": true
  },
  "microcontrast": {
    "enabled": true,
    "amount": 8
  },
  "sharpening": {
    "amount": 165
  },
  "vibrance": {
    "enabled": true,
    "pastels": 8,
    "saturated": 4,
    "protectskins": true,
    "avoidcolorshift": true
  }
}
```

## Planner Expected
```json
{
  "expected_global_change": 9.9,
  "expected_subject_hierarchy": 7.0,
  "expected_thumbnail_subject_read": 6.6,
  "expected_color_quality": 6.1,
  "expected_non_crop_tonal_improvement": 5.2,
  "expected_subject_separation_improvement": 7.0,
  "expected_color_intent_improvement": 5.7,
  "expected_highlight_shadow_quality": 4.0,
  "expected_composition_improvement": 4.0,
  "expected_crop_contribution": 2.0,
  "expected_naturalness": 8.0,
  "expected_artifact_free": 9.0,
  "crop_dependency": "secondary",
  "hierarchy_boost_applied": true,
  "visible_difference_score": 9.9,
  "hierarchy_improvement_score": 7.0
}
```

## Expected Effects
- primary subject should separate faster from poles/wires/background
- midtone rail/street geometry should gain clearer depth
- color presence should increase without fake HDR or phone-filter saturation

## Approved Curves
```json
[
  {
    "id": "tone_curve.midtone_pop_v1",
    "reason": "flat_midtone_geometry + low_thumbnail_impact + weak_subject_readability",
    "risk": "may increase harshness; checked by export gate",
    "intended_effect": "stronger midtone separation and subject depth"
  }
]
```

## Validation
```json
{
  "allowed": true,
  "blocked": [],
  "clamped": []
}
```

## Visual Verification Observed
```json
{
  "global_visible_difference_score": 8.0,
  "global_pixel_difference": 8.0,
  "subject_hierarchy_score": 6.5,
  "thumbnail_subject_read_score": 6.5,
  "color_quality_score": 8.0,
  "naturalness_score": 8.0,
  "artifact_free_score": 8.0,
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 5.8,
  "subject_separation_improvement": 6.5,
  "color_intent_improvement": 8.0,
  "highlight_shadow_quality": 6.0,
  "composition_improvement": 4.0,
  "crop_contribution": 2.0,
  "perceived_non_crop_improvement": "weak",
  "meaningful_non_crop_edit": false,
  "non_crop_quality_pass_count": 1,
  "non_crop_quality_pass_fields": [
    "color_intent_improvement"
  ],
  "crop_only_improvement": false,
  "non_crop_edit_quality": "fail",
  "non_crop_edit_quality_reason": "Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.",
  "hierarchy_boost_applied": false,
  "artifact_check": "pass",
  "decision": "failed_edit_quality",
  "export_gate_passed": false,
  "gate_requirements": {
    "meaningful_non_crop_requirements": {
      "minimum_score": 7.0,
      "minimum_pass_count": 2,
      "fields": [
        "subject_separation_improvement",
        "non_crop_tonal_improvement",
        "color_intent_improvement",
        "highlight_shadow_quality"
      ]
    },
    "subject_hierarchy_score_min": 7.0,
    "thumbnail_subject_read_score_min": 7.0,
    "artifact_free_score_min": 8.0,
    "naturalness_score_min": 7.0,
    "crop_dependency": "not primary",
    "crop_contribution_max_for_export": 6.9,
    "validation_allowed": true
  },
  "scoring_guidance": "Hierarchy score should answer: does the intended subject become easier and faster to read than competing structures?",
  "visible_difference_score": 8.0,
  "hierarchy_improvement_score": 6.5,
  "reason": "Phase 4.6 reclassification: predictive base remains proof-level. Tonal/color changes are visible numerically, but the main user-visible gain still reads as framing pressure relief rather than meaningful non-crop subject separation."
}
```
- Decision source: visual_verification

Non-crop edit quality: fail
Reason: Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.

## Export Gate
```json
{
  "global_visible_difference_score": 8.0,
  "global_pixel_difference": 8.0,
  "subject_hierarchy_score": 6.5,
  "thumbnail_subject_read_score": 6.5,
  "color_quality_score": 8.0,
  "naturalness_score": 8.0,
  "artifact_free_score": 8.0,
  "artifact_check": "pass",
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 5.8,
  "subject_separation_improvement": 6.5,
  "color_intent_improvement": 8.0,
  "highlight_shadow_quality": 6.0,
  "composition_improvement": 4.0,
  "crop_contribution": 2.0,
  "perceived_non_crop_improvement": "weak",
  "meaningful_non_crop_edit": false,
  "non_crop_quality_pass_count": 1,
  "non_crop_quality_pass_fields": [
    "color_intent_improvement"
  ],
  "crop_only_improvement": false,
  "non_crop_edit_quality": "fail",
  "non_crop_edit_quality_reason": "Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.",
  "hierarchy_boost_applied": false,
  "decision": "failed_edit_quality",
  "export_gate_passed": false,
  "gate_requirements": {
    "meaningful_non_crop_requirements": {
      "minimum_score": 7.0,
      "minimum_pass_count": 2,
      "fields": [
        "subject_separation_improvement",
        "non_crop_tonal_improvement",
        "color_intent_improvement",
        "highlight_shadow_quality"
      ]
    },
    "subject_hierarchy_score_min": 7.0,
    "thumbnail_subject_read_score_min": 7.0,
    "artifact_free_score_min": 8.0,
    "naturalness_score_min": 7.0,
    "crop_dependency": "not primary",
    "crop_contribution_max_for_export": 6.9,
    "validation_allowed": true
  },
  "scoring_guidance": "Hierarchy score should answer: does the intended subject become easier and faster to read than competing structures?",
  "visible_difference_score": 8.0,
  "hierarchy_improvement_score": 6.5,
  "export_requested": false,
  "runtime_decision": "failed_edit_quality",
  "decision_source": "visual_verification"
}
```

## Manual Score Comparison
```json
{
  "automated_scores": {
    "global_visible_difference_score": 8.0,
    "global_pixel_difference": 8.0,
    "subject_hierarchy_score": 6.5,
    "thumbnail_subject_read_score": 6.5,
    "color_quality_score": 8.0,
    "naturalness_score": 8.0,
    "artifact_free_score": 8.0,
    "artifact_check": "pass",
    "crop_dependency": "secondary",
    "non_crop_tonal_improvement": 5.8,
    "subject_separation_improvement": 6.5,
    "color_intent_improvement": 8.0,
    "highlight_shadow_quality": 6.0,
    "composition_improvement": 4.0,
    "crop_contribution": 2.0,
    "perceived_non_crop_improvement": "weak",
    "meaningful_non_crop_edit": false,
    "non_crop_quality_pass_count": 1,
    "non_crop_quality_pass_fields": [
      "color_intent_improvement"
    ],
    "crop_only_improvement": false,
    "non_crop_edit_quality": "fail",
    "non_crop_edit_quality_reason": "Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.",
    "hierarchy_boost_applied": false,
    "decision": "failed_edit_quality",
    "export_gate_passed": false,
    "gate_requirements": {
      "meaningful_non_crop_requirements": {
        "minimum_score": 7.0,
        "minimum_pass_count": 2,
        "fields": [
          "subject_separation_improvement",
          "non_crop_tonal_improvement",
          "color_intent_improvement",
          "highlight_shadow_quality"
        ]
      },
      "subject_hierarchy_score_min": 7.0,
      "thumbnail_subject_read_score_min": 7.0,
      "artifact_free_score_min": 8.0,
      "naturalness_score_min": 7.0,
      "crop_dependency": "not primary",
      "crop_contribution_max_for_export": 6.9,
      "validation_allowed": true
    },
    "scoring_guidance": "Hierarchy score should answer: does the intended subject become easier and faster to read than competing structures?",
    "visible_difference_score": 8.0,
    "hierarchy_improvement_score": 6.5,
    "export_requested": false,
    "runtime_decision": "failed_edit_quality",
    "decision_source": "visual_verification"
  },
  "human_scores": {
    "image": "IMG_1279",
    "brief": "warm natural travel edit; improve subject separation and color presence without fake HDR",
    "intensity": "medium",
    "visible_difference": 8.0,
    "hierarchy_improvement": 6.5,
    "color_quality": 8.0,
    "naturalness": 8.0,
    "artifact_free": 8.0,
    "crop_dependency": "none",
    "perceived_non_crop_improvement": "weak",
    "decision_correct": "no",
    "notes": "Phase 4.6 reclassification: predictive base remains proof-level. Tonal/color changes are visible numerically, but the main user-visible gain still reads as framing pressure relief rather than meaningful non-crop subject separation."
  },
  "score_delta": {
    "visible_difference": "+0.0",
    "hierarchy_improvement": "+0.0",
    "color_quality": "+0.0",
    "naturalness": "+0.0",
    "artifact_free": "+0.0",
    "decision_correct": "no"
  }
}
```

## Preview Files
- base_preview: `docs/evaluations/runs_phase6/IMG_1279/base_preview.jpg`
- predictive_preview: `docs/evaluations/runs_phase6/IMG_1279/predictive_preview.jpg`
- before_after: `docs/evaluations/runs_phase6/IMG_1279/before_after.jpg`
- profile: `docs/evaluations/runs_phase6/IMG_1279/predictive_profile.pp3`

## Visual Inspection Checklist
- Subject readability improved
- Thumbnail impact improved
- Sky/highlights remain believable
- No local-contrast crunch
- Not crop-only
