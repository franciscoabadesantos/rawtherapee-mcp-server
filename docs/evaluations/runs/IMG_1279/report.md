# Predictive Editor Evaluation

- raw_path: `/home/franciscosantos/Pictures/rawtherapee-output/IMG_1279.jpg`
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
  "visible_difference_score": 9.6,
  "hierarchy_improvement_score": 8.0,
  "artifact_check": "pass",
  "crop_dependency": "secondary",
  "decision": "export",
  "export_gate_passed": true,
  "export_requested": false,
  "runtime_decision": "preview_ready"
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
