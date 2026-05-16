# Predictive Editor Evaluation

- raw_path: `/mnt/c/Users/santo/Pictures/IMG_1279.CR3`
- source_type: `raw`
- is_raw_regression: `True`
- calibration_allowed: `True`
- brief: `warm natural travel edit; improve subject separation and color presence without fake HDR`
- intensity: `medium`
- style: `warm natural travel edit; improve subject separation and color presence without fake HDR`

## Diagnosis

## Planner / Prepare Output
```json
{
  "status": "verification_required",
  "decision": "verification_required",
  "decision_source": "auto_edit_manifest_select_prepare",
  "prepare_mode": "manifest_select",
  "raw_path": "/mnt/c/Users/santo/Pictures/IMG_1279.CR3",
  "profile_path": "/home/franciscosantos/.rawtherapee-mcp/custom_templates/img_1279_manifest_select.pp3",
  "base_preview_path": "/tmp/manifest_select_base_IMG_1279_1778883907167.jpg",
  "edited_preview_path": "/tmp/manifest_select_IMG_1279_1778883905269.jpg",
  "preview_path": "/tmp/manifest_select_IMG_1279_1778883905269.jpg",
  "before_after_path": "/tmp/manifest_select_compare_IMG_1279_1778883908313.jpg",
  "image_observation": {
    "main_subject": "green tram front entering the frame from the left rail corridor",
    "supporting_elements": [
      "converging rails",
      "overhead wire grid",
      "bright cloud mass behind the tram",
      "palms and roadside poles"
    ],
    "distractions": [
      "tall gray poles on the right",
      "busy wire lattice competing with the tram silhouette",
      "slightly muted grass and tram color"
    ],
    "tonal_state": "midtone geometry is a little flat and the tram does not separate as fast as the rails and poles suggest it should",
    "color_state": "natural but slightly restrained; the tram green and grass could carry more presence without becoming synthetic",
    "highlight_shadow_state": "cloud highlights are already bright but still believable; shadow detail is acceptable",
    "composition_state": "strong rail perspective already works, so the edit should improve subject hierarchy without relying on crop"
  },
  "vision_interpretation": {
    "user_goal": "make the tram read faster and give the frame stronger natural travel presence",
    "desired_viewer_first_read": "tram nose first, then rails and cloud depth",
    "desired_mood": "clean daylight travel image with stronger depth, not a filtered HDR look",
    "must_preserve": [
      "daylight realism",
      "clean cloud brightness",
      "tram color identity"
    ],
    "must_avoid": [
      "fake HDR",
      "local contrast crunch",
      "crop-only improvement",
      "cyan split in the sky"
    ]
  },
  "control_selections": [
    {
      "control_id": "Exposure.Curve",
      "approved_value_id": "tone_curve.midtone_depth_v1",
      "reason": "Use the approved midtone-depth curve to make the tram and rail geometry read faster without inventing a new curve.",
      "expected_effect": "clearer subject/background layering in the midtones",
      "risk": "sky and poles could become too hard",
      "risk_mitigation": "stay with the approved exact curve and keep other contrast lifts moderate"
    },
    {
      "control_id": "Exposure.Compensation",
      "value": 0.22,
      "reason": "Open the frame slightly so the tram face and carriage body read more immediately.",
      "expected_effect": "slightly brighter subject and cleaner first read",
      "risk": "highlights could flatten",
      "risk_mitigation": "keep the lift modest and avoid extra highlight compression unless needed"
    },
    {
      "control_id": "Exposure.Contrast",
      "value": 10,
      "reason": "Support the rail and tram geometry with moderate global contrast rather than coarse local contrast.",
      "expected_effect": "more defined subject silhouette and stronger rail structure",
      "risk": "blocked shadows and harsh poles",
      "risk_mitigation": "keep below the top of the manifest range and avoid stacking with aggressive sharpening"
    },
    {
      "control_id": "Luminance Curve.Enabled",
      "value": true,
      "reason": "Use the safer luminance-domain module for restrained depth shaping.",
      "expected_effect": "more separation without RGB color distortion",
      "risk": "nonlinear tone response",
      "risk_mitigation": "pair with avoid-color-shift and moderate contrast only"
    },
    {
      "control_id": "Luminance Curve.Contrast",
      "value": 8,
      "reason": "Add controlled midtone depth around the tram, rails, and cloud volume.",
      "expected_effect": "stronger luminance depth in the image core",
      "risk": "local harshness",
      "risk_mitigation": "stay in the middle of the validated range"
    },
    {
      "control_id": "Luminance Curve.AvoidColorShift",
      "value": true,
      "reason": "Protect the natural color relationships while increasing depth.",
      "expected_effect": "less hue drift while shaping luminance",
      "risk": "reduced effect",
      "risk_mitigation": "accept lower intensity in exchange for cleaner color"
    },
    {
      "control_id": "SharpenMicro.Enabled",
      "value": true,
      "reason": "Enable restrained microcontrast to support the tram front and rail texture.",
      "expected_effect": "slightly clearer fine structure",
      "risk": "grit and micro-halos",
      "risk_mitigation": "use a low amount and avoid local contrast"
    },
    {
      "control_id": "SharpenMicro.Amount",
      "value": 6,
      "reason": "Give the subject a little more edge definition without pushing into crunchy structure.",
      "expected_effect": "crisper but still natural detail",
      "risk": "wire and pole harshness",
      "risk_mitigation": "keep well below the top of the range"
    },
    {
      "control_id": "Vibrance.Enabled",
      "value": true,
      "reason": "Turn on vibrance so muted greens and travel color can lift selectively.",
      "expected_effect": "more color presence without a blanket saturation push",
      "risk": "color exaggeration",
      "risk_mitigation": "bias the move toward pastels instead of saturated colors"
    },
    {
      "control_id": "Vibrance.Pastels",
      "value": 7,
      "reason": "Strengthen low-saturation greens and sky transitions gently.",
      "expected_effect": "richer but still believable color",
      "risk": "pastel oversaturation",
      "risk_mitigation": "keep the number below the top half of the range"
    },
    {
      "control_id": "Vibrance.Saturated",
      "value": 3,
      "reason": "Avoid overdriving already bright parts of the frame while still giving color a lift.",
      "expected_effect": "controlled saturation support",
      "risk": "cartoonish rendering if too high",
      "risk_mitigation": "keep the saturated channel lift lower than the pastel lift"
    },
    {
      "control_id": "Vibrance.ProtectSkins",
      "value": true,
      "reason": "Use the manifest safety flag even though skin is minor in frame.",
      "expected_effect": "reduce odd hue shifts in people and reflections",
      "risk": "less vibrance impact",
      "risk_mitigation": "acceptable trade-off for cleaner color"
    },
    {
      "control_id": "Vibrance.AvoidColorShift",
      "value": true,
      "reason": "Keep the color lift natural rather than filter-like.",
      "expected_effect": "more stable hue relationships",
      "risk": "reduced color intensity",
      "risk_mitigation": "accept slightly lower force to preserve realism"
    }
  ],
  "controls_considered_but_rejected": [
    {
      "control_id": "Local Contrast.Amount",
      "reason": "Blocked by manifest due to prior artifact evidence and too likely to make wires and poles harsh."
    },
    {
      "control_id": "HSV Equalizer.HCurve",
      "reason": "Blocked by manifest and too easy to push the sky and tram green into a synthetic look."
    }
  ],
  "non_goals": [
    "do not create fake HDR",
    "do not rely on crop as the main improvement",
    "do not harden the cloud edges"
  ],
  "parameters": {
    "tone_curve": {
      "curve_mode": "Standard",
      "curve": "5;0;0;0.18;0.12;0.45;0.54;0.76;0.90;1;1;",
      "curve2": "0;"
    },
    "exposure": {
      "compensation": 0.22,
      "contrast": 10
    },
    "luminance_curve": {
      "enabled": true,
      "contrast": 8,
      "avoid_color_shift": true
    },
    "microcontrast": {
      "enabled": true,
      "amount": 6
    },
    "vibrance": {
      "enabled": true,
      "pastels": 7,
      "saturated": 3,
      "protectskins": true,
      "avoidcolorshift": true
    }
  },
  "validation": {
    "allowed": true,
    "blocked": [],
    "warnings": []
  },
  "verification_packet": {
    "subject": "green tram front entering the frame from the left rail corridor",
    "questions": [
      "Describe what changed around the main subject.",
      "Describe whether the subject separates more clearly from the background.",
      "Describe what changed in midtones.",
      "Describe what changed in highlights/shadows.",
      "Describe what changed in color.",
      "Describe any artifacts or unnatural effects.",
      "Is the visible improvement mostly crop/framing or tonal/color/detail?"
    ],
    "required_descriptions": [
      "subject_change_description",
      "midtone_change_description",
      "highlight_shadow_description",
      "color_change_description",
      "artifact_description",
      "crop_dependency_description"
    ],
    "score_fields_required": [
      "subject_separation_improvement",
      "non_crop_tonal_improvement",
      "color_intent_improvement",
      "highlight_shadow_quality",
      "composition_improvement",
      "crop_contribution",
      "perceived_non_crop_improvement",
      "artifact_check",
      "naturalness_score",
      "artifact_free_score"
    ]
  }
}
```

## Parameters
```json
{
  "tone_curve": {
    "curve_mode": "Standard",
    "curve": "5;0;0;0.18;0.12;0.45;0.54;0.76;0.90;1;1;",
    "curve2": "0;"
  },
  "exposure": {
    "compensation": 0.22,
    "contrast": 10
  },
  "luminance_curve": {
    "enabled": true,
    "contrast": 8,
    "avoid_color_shift": true
  },
  "microcontrast": {
    "enabled": true,
    "amount": 6
  },
  "vibrance": {
    "enabled": true,
    "pastels": 7,
    "saturated": 3,
    "protectskins": true,
    "avoidcolorshift": true
  }
}
```

## Planner Expected
```json
{}
```

## Expected Effects

## Validation
```json
{
  "allowed": true,
  "blocked": [],
  "warnings": []
}
```

## Visual Verification Observations
```json
{
  "subject_change_description": "The tram nose reads faster and the carriage body separates more clearly from the rails and wire grid without changing the composition.",
  "background_change_description": "The rails and cloud mass gain a little more layered depth, but the poles and wires remain believable rather than harsh.",
  "midtone_change_description": "Midtones are more structured through the tram body, rails, and grass corridor, giving the frame a stronger geometric read.",
  "highlight_shadow_description": "Cloud highlights stay believable and shadows do not block up noticeably.",
  "color_change_description": "The tram green and muted grass feel a touch richer and more travel-like without drifting into a fake filter look.",
  "artifact_description": "No obvious halos, crunchy edges, or cyan split appear in the sky or wire structure.",
  "crop_dependency_description": "The visible gain is tonal, color, and subject hierarchy rather than crop-driven.",
  "scores": {
    "global_pixel_difference": 8.1,
    "subject_separation_improvement": 7.1,
    "non_crop_tonal_improvement": 6.9,
    "color_intent_improvement": 7.8,
    "highlight_shadow_quality": 6.5,
    "composition_improvement": 4.0,
    "crop_contribution": 2.0,
    "perceived_non_crop_improvement": "moderate",
    "artifact_check": "pass",
    "naturalness_score": 8.0,
    "artifact_free_score": 8.0,
    "subject_hierarchy_score": 7.1,
    "thumbnail_subject_read_score": 6.9,
    "color_quality_score": 7.8
  }
}
```

## Visual Verification Scores
```json
{
  "global_visible_difference_score": 0.0,
  "global_pixel_difference": 8.1,
  "subject_hierarchy_score": 7.1,
  "thumbnail_subject_read_score": 6.9,
  "color_quality_score": 7.8,
  "naturalness_score": 8.0,
  "artifact_free_score": 8.0,
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 6.9,
  "subject_separation_improvement": 7.1,
  "color_intent_improvement": 7.8,
  "highlight_shadow_quality": 6.5,
  "composition_improvement": 4.0,
  "crop_contribution": 2.0,
  "perceived_non_crop_improvement": "moderate",
  "meaningful_non_crop_edit": true,
  "non_crop_quality_pass_count": 2,
  "non_crop_quality_pass_fields": [
    "subject_separation_improvement",
    "color_intent_improvement"
  ],
  "crop_only_improvement": false,
  "non_crop_edit_quality": "pass",
  "non_crop_edit_quality_reason": "subject separation, and color presence improve visibly before any crop is applied.",
  "hierarchy_boost_applied": false,
  "artifact_check": "pass",
  "decision": "proof_plus",
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
  "visible_difference_score": 0.0,
  "hierarchy_improvement_score": 7.1
}
```

## Consistency Checks
```json
{
  "warnings": [
    {
      "field": "artifact_free_score",
      "reason": "Descriptions mention potential artifacts/unnatural traits but artifact_free_score is 8.0"
    },
    {
      "field": "naturalness_score",
      "reason": "Descriptions mention potential artifacts/unnatural traits but naturalness_score is 8.0"
    },
    {
      "field": "artifact_check",
      "reason": "Descriptions mention artifact-like terms but artifact_check is pass"
    }
  ],
  "score_adjustments": []
}
```

## Final Decision
- Decision source: verify_predictive_edit
- Decision: proof_plus
Non-crop edit quality: pass
Reason: subject separation, and color presence improve visibly before any crop is applied.

## Export Gate
```json
{
  "global_visible_difference_score": 0.0,
  "global_pixel_difference": 8.1,
  "subject_hierarchy_score": 7.1,
  "thumbnail_subject_read_score": 6.9,
  "color_quality_score": 7.8,
  "naturalness_score": 8.0,
  "artifact_free_score": 8.0,
  "artifact_check": "pass",
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 6.9,
  "subject_separation_improvement": 7.1,
  "color_intent_improvement": 7.8,
  "highlight_shadow_quality": 6.5,
  "composition_improvement": 4.0,
  "crop_contribution": 2.0,
  "perceived_non_crop_improvement": "moderate",
  "meaningful_non_crop_edit": true,
  "non_crop_quality_pass_count": 2,
  "non_crop_quality_pass_fields": [
    "subject_separation_improvement",
    "color_intent_improvement"
  ],
  "crop_only_improvement": false,
  "non_crop_edit_quality": "pass",
  "non_crop_edit_quality_reason": "subject separation, and color presence improve visibly before any crop is applied.",
  "hierarchy_boost_applied": false,
  "decision": "proof_plus",
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
  "visible_difference_score": 0.0,
  "hierarchy_improvement_score": 7.1,
  "export_requested": false,
  "runtime_decision": "proof_plus",
  "decision_source": "verify_predictive_edit"
}
```

## Manual Score Comparison
```json
{
  "automated_scores": {
    "global_visible_difference_score": 0.0,
    "global_pixel_difference": 8.1,
    "subject_hierarchy_score": 7.1,
    "thumbnail_subject_read_score": 6.9,
    "color_quality_score": 7.8,
    "naturalness_score": 8.0,
    "artifact_free_score": 8.0,
    "artifact_check": "pass",
    "crop_dependency": "secondary",
    "non_crop_tonal_improvement": 6.9,
    "subject_separation_improvement": 7.1,
    "color_intent_improvement": 7.8,
    "highlight_shadow_quality": 6.5,
    "composition_improvement": 4.0,
    "crop_contribution": 2.0,
    "perceived_non_crop_improvement": "moderate",
    "meaningful_non_crop_edit": true,
    "non_crop_quality_pass_count": 2,
    "non_crop_quality_pass_fields": [
      "subject_separation_improvement",
      "color_intent_improvement"
    ],
    "crop_only_improvement": false,
    "non_crop_edit_quality": "pass",
    "non_crop_edit_quality_reason": "subject separation, and color presence improve visibly before any crop is applied.",
    "hierarchy_boost_applied": false,
    "decision": "proof_plus",
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
    "visible_difference_score": 0.0,
    "hierarchy_improvement_score": 7.1,
    "export_requested": false,
    "runtime_decision": "proof_plus",
    "decision_source": "verify_predictive_edit"
  },
  "human_scores": {
    "image": "IMG_1279",
    "brief": "warm natural travel edit; improve subject separation and color presence without fake HDR",
    "intensity": "medium",
    "visible_difference": 8.3,
    "hierarchy_improvement": 6.9,
    "color_quality": 8.1,
    "naturalness": 8.0,
    "artifact_free": 8.0,
    "crop_dependency": "none",
    "non_crop_tonal_improvement": 7.0,
    "subject_separation_improvement": 7.2,
    "thumbnail_subject_read_score": 6.9,
    "color_intent_improvement": 8.1,
    "highlight_shadow_quality": 6.6,
    "composition_improvement": 4.0,
    "crop_contribution": 2.0,
    "perceived_non_crop_improvement": "moderate",
    "decision_correct": "yes",
    "notes": "Tram readability improves before any crop, rails and street midtones gain layered depth, color presence is stronger, highlights and shadows stay believable, no obvious artifact pattern appears, and the gain reads as tonal rather than framing-driven."
  },
  "score_delta": {
    "visible_difference": "-8.3",
    "hierarchy_improvement": "+0.2",
    "color_quality": "-0.3",
    "naturalness": "+0.0",
    "artifact_free": "+0.0",
    "non_crop_tonal_improvement": "-0.1",
    "subject_separation_improvement": "-0.1",
    "color_intent_improvement": "-0.3",
    "highlight_shadow_quality": "-0.1",
    "composition_improvement": "+0.0",
    "crop_contribution": "+0.0",
    "decision_correct": "yes"
  }
}
```

## Rendered Preview Files
- base_preview: `docs/evaluations/runs_phase10/IMG_1279/base_preview.jpg`
- predictive_preview: `docs/evaluations/runs_phase10/IMG_1279/predictive_preview.jpg`
- before_after: `docs/evaluations/runs_phase10/IMG_1279/before_after.jpg`
- profile: `docs/evaluations/runs_phase10/IMG_1279/predictive_profile.pp3`

## Inline Image Availability
```json
{
  "prepare": {
    "attachment_available": true,
    "image_count": 3,
    "content_types": [
      "text",
      "image",
      "image",
      "image"
    ]
  },
  "verify": {
    "attachment_available": true,
    "image_count": 3,
    "content_types": [
      "text",
      "image",
      "image",
      "image"
    ]
  }
}
```

## Visual Inspection Checklist
- Subject readability improved
- Thumbnail impact improved
- Sky/highlights remain believable
- No local-contrast crunch
- Not crop-only
