# Predictive Editor Evaluation

- raw_path: `/mnt/c/Users/santo/Pictures/IMG_1850.CR3`
- source_type: `raw`
- is_raw_regression: `True`
- calibration_allowed: `True`
- brief: `landscape cleanup with controlled sky highlights, reduced haze, and natural tonal depth`
- intensity: `medium`
- style: `landscape cleanup with controlled sky highlights, reduced haze, and natural tonal depth`

## Diagnosis
- dull_color_presence (severity=0.45): Brief/style requests stronger but natural color presence.
- bright_sky_needs_control (severity=0.35): Bright sky/cloud wording suggests highlight containment.

## Parameters
```json
{
  "luminance_curve": {
    "enabled": true,
    "contrast": 12,
    "avoid_color_shift": true,
    "lh_curve": "5;0;0;0.16;0.10;0.46;0.52;0.76;0.88;1;1;",
    "hh_curve": "5;0;0;0.28;0.24;0.60;0.52;0.82;0.74;1;0.90;"
  },
  "vibrance": {
    "enabled": true,
    "pastels": 8,
    "saturated": 4,
    "protectskins": true,
    "avoidcolorshift": true
  },
  "exposure": {
    "saturation": 4,
    "highlight_compression": 6
  },
  "highlight_rolloff": {
    "highlight_compression_threshold": 9,
    "highlights": -6,
    "highlight_tonal_width": 55,
    "radius": 46
  }
}
```

## Planner Expected
```json
{
  "expected_global_change": 7.7,
  "expected_subject_hierarchy": 4.4,
  "expected_thumbnail_subject_read": 4.6,
  "expected_color_quality": 6.1,
  "expected_non_crop_tonal_improvement": 4.8,
  "expected_subject_separation_improvement": 4.4,
  "expected_color_intent_improvement": 5.7,
  "expected_highlight_shadow_quality": 5.4,
  "expected_composition_improvement": 4.0,
  "expected_crop_contribution": 2.0,
  "expected_naturalness": 8.0,
  "expected_artifact_free": 9.0,
  "crop_dependency": "secondary",
  "hierarchy_boost_applied": false,
  "visible_difference_score": 7.7,
  "hierarchy_improvement_score": 4.4
}
```

## Expected Effects
- color presence should increase without fake HDR or phone-filter saturation
- bright sky/highlights should stay more believable

## Approved Curves
```json
[
  {
    "id": "luminance_curve.landscape_depth_v1",
    "reason": "bright_sky_needs_control + landscape_sky",
    "risk": "may make haze transitions or cloud edges feel too hard if stacked with strong contrast",
    "intended_effect": "increase landscape and midtone depth while preserving natural color relationships"
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
  "global_visible_difference_score": 6.1,
  "global_pixel_difference": 6.1,
  "subject_hierarchy_score": 5.3,
  "thumbnail_subject_read_score": 5.2,
  "color_quality_score": 6.2,
  "naturalness_score": 8.5,
  "artifact_free_score": 9.0,
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 6.3,
  "subject_separation_improvement": 5.3,
  "color_intent_improvement": 6.4,
  "highlight_shadow_quality": 6.6,
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
  "visible_difference_score": 6.1,
  "hierarchy_improvement_score": 5.3,
  "reason": "The stronger landscape tonal-depth preset adds some cloud and hillside definition, but the haze and broad landscape hierarchy still read as only mildly improved."
}
```
- Decision source: visual_verification

Non-crop edit quality: fail
Reason: Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.

## Export Gate
```json
{
  "global_visible_difference_score": 6.1,
  "global_pixel_difference": 6.1,
  "subject_hierarchy_score": 5.3,
  "thumbnail_subject_read_score": 5.2,
  "color_quality_score": 6.2,
  "naturalness_score": 8.5,
  "artifact_free_score": 9.0,
  "artifact_check": "pass",
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 6.3,
  "subject_separation_improvement": 5.3,
  "color_intent_improvement": 6.4,
  "highlight_shadow_quality": 6.6,
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
  "visible_difference_score": 6.1,
  "hierarchy_improvement_score": 5.3,
  "export_requested": false,
  "runtime_decision": "failed_edit_quality",
  "decision_source": "visual_verification"
}
```

## Manual Score Comparison
```json
{
  "automated_scores": {
    "global_visible_difference_score": 6.1,
    "global_pixel_difference": 6.1,
    "subject_hierarchy_score": 5.3,
    "thumbnail_subject_read_score": 5.2,
    "color_quality_score": 6.2,
    "naturalness_score": 8.5,
    "artifact_free_score": 9.0,
    "artifact_check": "pass",
    "crop_dependency": "secondary",
    "non_crop_tonal_improvement": 6.3,
    "subject_separation_improvement": 5.3,
    "color_intent_improvement": 6.4,
    "highlight_shadow_quality": 6.6,
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
    "visible_difference_score": 6.1,
    "hierarchy_improvement_score": 5.3,
    "export_requested": false,
    "runtime_decision": "failed_edit_quality",
    "decision_source": "visual_verification"
  },
  "human_scores": {
    "image": "IMG_1850",
    "brief": "landscape cleanup with controlled sky highlights, reduced haze, and natural tonal depth",
    "intensity": "medium",
    "visible_difference": 6.1,
    "hierarchy_improvement": 5.3,
    "color_quality": 6.2,
    "naturalness": 8.5,
    "artifact_free": 9.0,
    "crop_dependency": "none",
    "non_crop_tonal_improvement": 6.3,
    "subject_separation_improvement": 5.3,
    "thumbnail_subject_read_score": 5.2,
    "color_intent_improvement": 6.4,
    "highlight_shadow_quality": 6.6,
    "composition_improvement": 4.0,
    "crop_contribution": 1.0,
    "perceived_non_crop_improvement": "weak",
    "decision_correct": "yes",
    "notes": "The stronger landscape tonal-depth preset adds some cloud and hillside definition, but the haze and broad landscape hierarchy still read as only mildly improved."
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
- base_preview: `docs/evaluations/runs_phase6/IMG_1850/base_preview.jpg`
- predictive_preview: `docs/evaluations/runs_phase6/IMG_1850/predictive_preview.jpg`
- before_after: `docs/evaluations/runs_phase6/IMG_1850/before_after.jpg`
- profile: `docs/evaluations/runs_phase6/IMG_1850/predictive_profile.pp3`

## Visual Inspection Checklist
- Subject readability improved
- Thumbnail impact improved
- Sky/highlights remain believable
- No local-contrast crunch
- Not crop-only
