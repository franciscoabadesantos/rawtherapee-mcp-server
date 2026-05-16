# Predictive Editor Evaluation

- raw_path: `/mnt/c/Users/santo/Pictures/IMG_3709.CR3`
- source_type: `raw`
- is_raw_regression: `True`
- calibration_allowed: `True`
- brief: `low-light natural recovery with readable subject separation and restrained shadow lift`
- intensity: `low`
- style: `low-light natural recovery with readable subject separation and restrained shadow lift`

## Diagnosis

## Planner / Prepare Output
```json
{
  "status": "verification_required",
  "decision": "verification_required",
  "decision_source": "auto_edit_manifest_select_prepare",
  "prepare_mode": "manifest_select",
  "raw_path": "/mnt/c/Users/santo/Pictures/IMG_3709.CR3",
  "profile_path": "/home/franciscosantos/.rawtherapee-mcp/custom_templates/img_3709_manifest_select.pp3",
  "base_preview_path": "/tmp/manifest_select_base_IMG_3709_1778883913251.jpg",
  "edited_preview_path": "/tmp/manifest_select_IMG_3709_1778883911822.jpg",
  "preview_path": "/tmp/manifest_select_IMG_3709_1778883911822.jpg",
  "before_after_path": "/tmp/manifest_select_compare_IMG_3709_1778883914172.jpg",
  "image_observation": {
    "main_subject": "person standing on the beach at dusk",
    "supporting_elements": [
      "sand texture",
      "dark cliff line",
      "soft dusk sky",
      "distant rescue ring structure"
    ],
    "distractions": [
      "subject face and body fall into shadow",
      "overall frame is low-contrast and low-light",
      "noise risk if shadows are lifted too hard"
    ],
    "tonal_state": "the subject is under-read and the scene is dim, but the darkness is part of the mood",
    "color_state": "warm dusk tone is natural and should stay restrained",
    "highlight_shadow_state": "there are no aggressive highlights; the main danger is milky shadow lift and noisy low-light structure",
    "composition_state": "the composition is already about the person in open space, so the edit should improve subject readability without changing the framing logic"
  },
  "vision_interpretation": {
    "user_goal": "recover the low-light image naturally so the subject reads better while keeping the dusk feeling intact",
    "desired_viewer_first_read": "person first, then beach and cliff context",
    "desired_mood": "quiet dusk realism, not flash-lit rescue",
    "must_preserve": [
      "dusk atmosphere",
      "shadow mood",
      "natural skin and beach color"
    ],
    "must_avoid": [
      "crunchy noise",
      "over-bright shadows",
      "plastic smoothing",
      "crop-only improvement"
    ]
  },
  "control_selections": [
    {
      "control_id": "Luminance Curve.lhCurve",
      "approved_value_id": "luminance_curve.low_light_lift_v1",
      "reason": "Use the approved low-light tonal-depth preset as the safest subject-facing lift available in the manifest.",
      "expected_effect": "slightly easier subject read without flattening the frame",
      "risk": "noise becomes more obvious",
      "risk_mitigation": "use the approved exact preset and avoid stronger local shadow recovery"
    },
    {
      "control_id": "Exposure.Compensation",
      "value": 0.16,
      "reason": "Open the frame a little so the subject face and torso rise out of the dusk floor.",
      "expected_effect": "slightly brighter subject read",
      "risk": "losing the dusk mood",
      "risk_mitigation": "keep the lift very small"
    },
    {
      "control_id": "Exposure.Saturation",
      "value": 2,
      "reason": "Give the dusk frame a small color reinforcement without making it glow artificially.",
      "expected_effect": "slightly stronger warm dusk color",
      "risk": "artificial sunset color",
      "risk_mitigation": "keep the number low and avoid extra WB shifts"
    },
    {
      "control_id": "Vibrance.Enabled",
      "value": true,
      "reason": "Use selective color support instead of a heavy global saturation move.",
      "expected_effect": "a little more color presence in the low-saturation dusk tones",
      "risk": "color noise or odd hue drift",
      "risk_mitigation": "keep both vibrance amounts restrained"
    },
    {
      "control_id": "Vibrance.Pastels",
      "value": 4,
      "reason": "Lift the muted dusk tones slightly so the frame feels less dead.",
      "expected_effect": "gentle pastel color presence",
      "risk": "noisy or fake color",
      "risk_mitigation": "stay low and do not push saturated colors"
    },
    {
      "control_id": "Vibrance.Saturated",
      "value": 1,
      "reason": "Keep the already-dark scene from turning overly stylized.",
      "expected_effect": "minimal support for stronger hues",
      "risk": "cartoon color if overdone",
      "risk_mitigation": "set near the bottom of the range"
    }
  ],
  "controls_considered_but_rejected": [
    {
      "control_id": "Shadows & Highlights.Shadows",
      "reason": "Available but pending-evidence and likely to create milky shadows or noise in this low-light frame."
    },
    {
      "control_id": "Local Contrast.Amount",
      "reason": "Blocked by manifest and too risky for high-ISO dusk texture."
    },
    {
      "control_id": "Retinex",
      "reason": "A more capable local low-light recovery family might help the subject, but it is not available in the current manifest."
    }
  ],
  "non_goals": [
    "do not brighten the beach like daylight",
    "do not create crunchy noise",
    "do not rely on crop as the main improvement"
  ],
  "parameters": {
    "luminance_curve": {
      "enabled": true,
      "contrast": 9,
      "avoid_color_shift": true,
      "lh_curve": "5;0;0;0.14;0.22;0.40;0.52;0.72;0.84;1;1;",
      "hh_curve": "5;0;0;0.30;0.28;0.66;0.60;0.86;0.82;1;0.96;"
    },
    "exposure": {
      "compensation": 0.16,
      "saturation": 2
    },
    "vibrance": {
      "enabled": true,
      "pastels": 4,
      "saturated": 1
    }
  },
  "validation": {
    "allowed": true,
    "blocked": [],
    "warnings": []
  },
  "verification_packet": {
    "subject": "person standing on the beach at dusk",
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
  "luminance_curve": {
    "enabled": true,
    "contrast": 9,
    "avoid_color_shift": true,
    "lh_curve": "5;0;0;0.14;0.22;0.40;0.52;0.72;0.84;1;1;",
    "hh_curve": "5;0;0;0.30;0.28;0.66;0.60;0.86;0.82;1;0.96;"
  },
  "exposure": {
    "compensation": 0.16,
    "saturation": 2
  },
  "vibrance": {
    "enabled": true,
    "pastels": 4,
    "saturated": 1
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
  "subject_change_description": "The person becomes slightly easier to read against the sand, but the frame still feels intentionally dim and subdued.",
  "background_change_description": "The beach and cliff context change only a little, which keeps the dusk mood intact.",
  "midtone_change_description": "There is a small lift in the subject-facing midtones, but not enough to create a strong non-crop transformation.",
  "highlight_shadow_description": "Highlights remain calm and the shadow lift stays restrained, avoiding a milky look.",
  "color_change_description": "Warm dusk color is only slightly stronger and remains natural.",
  "artifact_description": "No obvious noise crunch, plastic smoothing, or halo pattern is introduced, but the gain remains modest.",
  "crop_dependency_description": "The change is not crop-driven; it is simply a small tonal recovery that does not cross into a strong edit.",
  "scores": {
    "global_pixel_difference": 4.9,
    "subject_separation_improvement": 4.5,
    "non_crop_tonal_improvement": 4.9,
    "color_intent_improvement": 5.0,
    "highlight_shadow_quality": 5.1,
    "composition_improvement": 4.0,
    "crop_contribution": 1.0,
    "perceived_non_crop_improvement": "weak",
    "artifact_check": "pass",
    "naturalness_score": 8.3,
    "artifact_free_score": 9.0,
    "subject_hierarchy_score": 4.5,
    "thumbnail_subject_read_score": 4.4,
    "color_quality_score": 5.0
  }
}
```

## Visual Verification Scores
```json
{
  "global_visible_difference_score": 0.0,
  "global_pixel_difference": 4.9,
  "subject_hierarchy_score": 4.5,
  "thumbnail_subject_read_score": 4.4,
  "color_quality_score": 5.0,
  "naturalness_score": 8.3,
  "artifact_free_score": 9.0,
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 4.9,
  "subject_separation_improvement": 4.5,
  "color_intent_improvement": 5.0,
  "highlight_shadow_quality": 5.1,
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
  "visible_difference_score": 0.0,
  "hierarchy_improvement_score": 4.5
}
```

## Consistency Checks
```json
{
  "warnings": [
    {
      "field": "artifact_free_score",
      "reason": "Descriptions mention potential artifacts/unnatural traits but artifact_free_score is 9.0"
    },
    {
      "field": "naturalness_score",
      "reason": "Descriptions mention potential artifacts/unnatural traits but naturalness_score is 8.3"
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
- Decision: proof_only
Non-crop edit quality: fail
Reason: Tonal/color changes are numerically visible but do not materially improve subject separation or visual intent.

## Export Gate
```json
{
  "global_visible_difference_score": 0.0,
  "global_pixel_difference": 4.9,
  "subject_hierarchy_score": 4.5,
  "thumbnail_subject_read_score": 4.4,
  "color_quality_score": 5.0,
  "naturalness_score": 8.3,
  "artifact_free_score": 9.0,
  "artifact_check": "pass",
  "crop_dependency": "secondary",
  "non_crop_tonal_improvement": 4.9,
  "subject_separation_improvement": 4.5,
  "color_intent_improvement": 5.0,
  "highlight_shadow_quality": 5.1,
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
  "visible_difference_score": 0.0,
  "hierarchy_improvement_score": 4.5,
  "export_requested": false,
  "runtime_decision": "proof_only",
  "decision_source": "verify_predictive_edit"
}
```

## Manual Score Comparison
```json
{
  "automated_scores": {
    "global_visible_difference_score": 0.0,
    "global_pixel_difference": 4.9,
    "subject_hierarchy_score": 4.5,
    "thumbnail_subject_read_score": 4.4,
    "color_quality_score": 5.0,
    "naturalness_score": 8.3,
    "artifact_free_score": 9.0,
    "artifact_check": "pass",
    "crop_dependency": "secondary",
    "non_crop_tonal_improvement": 4.9,
    "subject_separation_improvement": 4.5,
    "color_intent_improvement": 5.0,
    "highlight_shadow_quality": 5.1,
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
    "visible_difference_score": 0.0,
    "hierarchy_improvement_score": 4.5,
    "export_requested": false,
    "runtime_decision": "proof_only",
    "decision_source": "verify_predictive_edit"
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
    "notes": "The subject becomes slightly easier to read, low-light midtones lift a little, highlights and shadows remain restrained, color is only slightly stronger, no obvious artifact pattern appears, and the gain remains modest rather than a meaningful non-crop improvement."
  },
  "score_delta": {
    "visible_difference": "-5.0",
    "hierarchy_improvement": "-0.1",
    "color_quality": "+0.0",
    "naturalness": "+0.0",
    "artifact_free": "+0.0",
    "non_crop_tonal_improvement": "-0.1",
    "subject_separation_improvement": "-0.1",
    "color_intent_improvement": "-0.1",
    "highlight_shadow_quality": "+0.1",
    "composition_improvement": "+0.0",
    "crop_contribution": "+0.0",
    "decision_correct": "yes"
  }
}
```

## Rendered Preview Files
- base_preview: `docs/evaluations/runs_phase10/IMG_3709/base_preview.jpg`
- predictive_preview: `docs/evaluations/runs_phase10/IMG_3709/predictive_preview.jpg`
- before_after: `docs/evaluations/runs_phase10/IMG_3709/before_after.jpg`
- profile: `docs/evaluations/runs_phase10/IMG_3709/predictive_profile.pp3`

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
