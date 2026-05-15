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
  "exposure": {
    "contrast": 9,
    "compensation": 0.322,
    "saturation": 4
  },
  "luminance_curve": {
    "enabled": true,
    "contrast": 5
  },
  "microcontrast": {
    "enabled": true,
    "amount": 6
  },
  "sharpening": {
    "amount": 165
  },
  "vibrance": {
    "enabled": true,
    "pastels": 4,
    "saturated": 4,
    "protectskins": true,
    "avoidcolorshift": true
  }
}
```

## Expected Effects
- subject readability should improve at thumbnail scale
- midtone geometry should separate more clearly
- color presence should improve without phone-filter intensity

## Validation
```json
{
  "allowed": true,
  "blocked": [],
  "clamped": []
}
```

## Export Gate
```json
{
  "global_visible_difference_score": 9.6,
  "subject_hierarchy_score": 6.4,
  "thumbnail_subject_read_score": 6.4,
  "color_quality_score": 7.1,
  "naturalness_score": 8.0,
  "artifact_free_score": 9.0,
  "artifact_check": "pass",
  "crop_dependency": "secondary",
  "decision": "proof_plus",
  "export_gate_passed": false,
  "gate_requirements": {
    "subject_hierarchy_score_min": 7.0,
    "thumbnail_subject_read_score_min": 7.0,
    "artifact_free_score_min": 8.0,
    "naturalness_score_min": 7.0,
    "crop_dependency": "not primary",
    "validation_allowed": true
  },
  "scoring_guidance": "Hierarchy score should answer: does the intended subject become easier and faster to read than competing structures?",
  "visible_difference_score": 9.6,
  "hierarchy_improvement_score": 6.4,
  "export_requested": false,
  "runtime_decision": "proof_plus"
}
```

## Manual Score Comparison
```json
{
  "automated_scores": {
    "global_visible_difference_score": 9.6,
    "subject_hierarchy_score": 6.4,
    "thumbnail_subject_read_score": 6.4,
    "color_quality_score": 7.1,
    "naturalness_score": 8.0,
    "artifact_free_score": 9.0,
    "artifact_check": "pass",
    "crop_dependency": "secondary",
    "decision": "proof_plus",
    "export_gate_passed": false,
    "gate_requirements": {
      "subject_hierarchy_score_min": 7.0,
      "thumbnail_subject_read_score_min": 7.0,
      "artifact_free_score_min": 8.0,
      "naturalness_score_min": 7.0,
      "crop_dependency": "not primary",
      "validation_allowed": true
    },
    "scoring_guidance": "Hierarchy score should answer: does the intended subject become easier and faster to read than competing structures?",
    "visible_difference_score": 9.6,
    "hierarchy_improvement_score": 6.4,
    "export_requested": false,
    "runtime_decision": "proof_plus"
  },
  "human_scores": {
    "image": "IMG_1279",
    "brief": "warm natural travel edit; improve subject separation and color presence without fake HDR",
    "intensity": "medium",
    "visible_difference": 7.0,
    "hierarchy_improvement": 6.0,
    "color_quality": 7.0,
    "naturalness": 8.0,
    "artifact_free": 8.0,
    "crop_dependency": "none",
    "decision_correct": "yes",
    "notes": "Visible non-crop tonal/color improvement; banned controls absent; hierarchy gain remains below export threshold, so proof_plus is the correct decision."
  },
  "score_delta": {
    "visible_difference": "+2.6",
    "hierarchy_improvement": "+0.4",
    "color_quality": "+0.1",
    "naturalness": "+0.0",
    "artifact_free": "+1.0",
    "decision_correct": "yes"
  }
}
```

## Preview Files
- base_preview: `docs/evaluations/runs/IMG_1279/base_preview.jpg`
- predictive_preview: `docs/evaluations/runs/IMG_1279/predictive_preview.jpg`
- before_after: `docs/evaluations/runs/IMG_1279/before_after.jpg`
- profile: `docs/evaluations/runs/IMG_1279/predictive_profile.pp3`

## Visual Inspection Checklist
- Subject readability improved
- Thumbnail impact improved
- Sky/highlights remain believable
- No local-contrast crunch
- Not crop-only
