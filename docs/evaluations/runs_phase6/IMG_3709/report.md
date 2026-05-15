# Predictive Editor Evaluation

- raw_path: `/mnt/c/Users/santo/Pictures/IMG_3709.CR3`
- source_type: `raw`
- is_raw_regression: `True`
- calibration_allowed: `True`
- brief: `low-light natural recovery with readable subject separation and restrained shadow lift`
- intensity: `low`
- style: `low-light natural recovery with readable subject separation and restrained shadow lift`

## Diagnosis
- dull_color_presence (severity=0.45): Brief/style requests stronger but natural color presence.

## Parameters
```json
{
  "luminance_curve": {
    "enabled": true,
    "contrast": 9,
    "avoid_color_shift": true,
    "lh_curve": "5;0;0;0.14;0.22;0.40;0.52;0.72;0.84;1;1;",
    "hh_curve": "5;0;0;0.30;0.28;0.66;0.60;0.86;0.82;1;0.96;"
  },
  "vibrance": {
    "enabled": true,
    "pastels": 5,
    "saturated": 3,
    "protectskins": true,
    "avoidcolorshift": true
  },
  "exposure": {
    "saturation": 3
  }
}
```

## Planner Expected
```json
{
  "expected_global_change": 6.9,
  "expected_subject_hierarchy": 4.4,
  "expected_thumbnail_subject_read": 4.6,
  "expected_color_quality": 6.1,
  "expected_non_crop_tonal_improvement": 4.1,
  "expected_subject_separation_improvement": 4.4,
  "expected_color_intent_improvement": 5.7,
  "expected_highlight_shadow_quality": 4.0,
  "expected_composition_improvement": 4.0,
  "expected_crop_contribution": 2.0,
  "expected_naturalness": 8.0,
  "expected_artifact_free": 9.0,
  "crop_dependency": "secondary",
  "hierarchy_boost_applied": false,
  "visible_difference_score": 6.9,
  "hierarchy_improvement_score": 4.4
}
```

## Expected Effects
- color presence should increase without fake HDR or phone-filter saturation

## Approved Curves
```json
[
  {
    "id": "luminance_curve.low_light_lift_v1",
    "reason": "low_light_high_iso",
    "risk": "can make low-light noise more obvious if used aggressively",
    "intended_effect": "lift subject-facing low-light midtones without washing out shadows or amplifying color drift"
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
  "global_visible_difference_score": 5.0,
  "global_pixel_difference": 5.0,
  "subject_hierarchy_score": 4.6,
  "thumbnail_subject_read_score": 4.5,
  "color_quality_score": 5.0,
  "naturalness_score": 8.3,
  "artifact_free_score": 9.0,
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 5.0,
  "subject_separation_improvement": 4.6,
  "color_intent_improvement": 5.1,
  "highlight_shadow_quality": 5.0,
  "composition_improvement": 4.0,
  "crop_contribution": 1.0,
  "perceived_non_crop_improvement": "weak",
  "meaningful_non_crop_edit": false,
  "non_crop_quality_pass_count": 0,
  "non_crop_quality_pass_fields": [],
  "crop_only_improvement": false,
  "non_crop_edit_quality": "fail",
  "non_crop_edit_quality_reason": "Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.",
  "hierarchy_boost_applied": false,
  "artifact_check": "pass",
  "decision": "proof_only",
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
  "visible_difference_score": 5.0,
  "hierarchy_improvement_score": 4.6,
  "reason": "The low-light tonal-depth preset makes the subject slightly easier to read, but the gain remains modest and does not create a meaningful non-crop edit."
}
```
- Decision source: visual_verification

Non-crop edit quality: fail
Reason: Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.

## Export Gate
```json
{
  "global_visible_difference_score": 5.0,
  "global_pixel_difference": 5.0,
  "subject_hierarchy_score": 4.6,
  "thumbnail_subject_read_score": 4.5,
  "color_quality_score": 5.0,
  "naturalness_score": 8.3,
  "artifact_free_score": 9.0,
  "artifact_check": "pass",
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 5.0,
  "subject_separation_improvement": 4.6,
  "color_intent_improvement": 5.1,
  "highlight_shadow_quality": 5.0,
  "composition_improvement": 4.0,
  "crop_contribution": 1.0,
  "perceived_non_crop_improvement": "weak",
  "meaningful_non_crop_edit": false,
  "non_crop_quality_pass_count": 0,
  "non_crop_quality_pass_fields": [],
  "crop_only_improvement": false,
  "non_crop_edit_quality": "fail",
  "non_crop_edit_quality_reason": "Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.",
  "hierarchy_boost_applied": false,
  "decision": "proof_only",
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
  "visible_difference_score": 5.0,
  "hierarchy_improvement_score": 4.6,
  "export_requested": false,
  "runtime_decision": "proof_only",
  "decision_source": "visual_verification"
}
```

## Manual Score Comparison
```json
{
  "automated_scores": {
    "global_visible_difference_score": 5.0,
    "global_pixel_difference": 5.0,
    "subject_hierarchy_score": 4.6,
    "thumbnail_subject_read_score": 4.5,
    "color_quality_score": 5.0,
    "naturalness_score": 8.3,
    "artifact_free_score": 9.0,
    "artifact_check": "pass",
    "crop_dependency": "secondary",
    "non_crop_tonal_improvement": 5.0,
    "subject_separation_improvement": 4.6,
    "color_intent_improvement": 5.1,
    "highlight_shadow_quality": 5.0,
    "composition_improvement": 4.0,
    "crop_contribution": 1.0,
    "perceived_non_crop_improvement": "weak",
    "meaningful_non_crop_edit": false,
    "non_crop_quality_pass_count": 0,
    "non_crop_quality_pass_fields": [],
    "crop_only_improvement": false,
    "non_crop_edit_quality": "fail",
    "non_crop_edit_quality_reason": "Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.",
    "hierarchy_boost_applied": false,
    "decision": "proof_only",
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
    "visible_difference_score": 5.0,
    "hierarchy_improvement_score": 4.6,
    "export_requested": false,
    "runtime_decision": "proof_only",
    "decision_source": "visual_verification"
  },
  "human_scores": {
    "image": "IMG_3709",
    "brief": "low-light natural recovery with readable subject separation and restrained shadow lift",
    "intensity": "low",
    "visible_difference": 5.0,
    "hierarchy_improvement": 4.6,
    "color_quality": 5.0,
    "naturalness": 8.3,
    "artifact_free": 9.0,
    "crop_dependency": "none",
    "non_crop_tonal_improvement": 5.0,
    "subject_separation_improvement": 4.6,
    "thumbnail_subject_read_score": 4.5,
    "color_intent_improvement": 5.1,
    "highlight_shadow_quality": 5.0,
    "composition_improvement": 4.0,
    "crop_contribution": 1.0,
    "perceived_non_crop_improvement": "weak",
    "decision_correct": "yes",
    "notes": "The low-light tonal-depth preset makes the subject slightly easier to read, but the gain remains modest and does not create a meaningful non-crop edit."
  },
  "score_delta": {
    "visible_difference": "+0.0",
    "hierarchy_improvement": "+0.0",
    "color_quality": "+0.0",
    "naturalness": "+0.0",
    "artifact_free": "+0.0",
    "non_crop_tonal_improvement": "+0.0",
    "subject_separation_improvement": "+0.0",
    "color_intent_improvement": "+0.0",
    "highlight_shadow_quality": "+0.0",
    "composition_improvement": "+0.0",
    "crop_contribution": "+0.0",
    "decision_correct": "yes"
  }
}
```

## Preview Files
- base_preview: `docs/evaluations/runs_phase6/IMG_3709/base_preview.jpg`
- predictive_preview: `docs/evaluations/runs_phase6/IMG_3709/predictive_preview.jpg`
- before_after: `docs/evaluations/runs_phase6/IMG_3709/before_after.jpg`
- profile: `docs/evaluations/runs_phase6/IMG_3709/predictive_profile.pp3`

## Visual Inspection Checklist
- Subject readability improved
- Thumbnail impact improved
- Sky/highlights remain believable
- No local-contrast crunch
- Not crop-only
