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

## Expected Effects
- primary subject should separate faster from poles/wires/background
- midtone rail/street geometry should gain clearer depth
- color presence should increase without fake HDR or phone-filter saturation

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
  "hierarchy_boost_applied": true,
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
    "hierarchy_boost_applied": true,
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
    "visible_difference": 8.0,
    "hierarchy_improvement": 6.5,
    "color_quality": 8.0,
    "naturalness": 8.0,
    "artifact_free": 8.0,
    "crop_dependency": "none",
    "decision_correct": "yes",
    "notes": "Phase 4 CR3 run: stronger safe hierarchy edit with boost applied; still below export threshold because poles/wires/sky continue to compete with the tram at thumbnail scale."
  },
  "score_delta": {
    "visible_difference": "+1.6",
    "hierarchy_improvement": "-0.1",
    "color_quality": "-0.9",
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
