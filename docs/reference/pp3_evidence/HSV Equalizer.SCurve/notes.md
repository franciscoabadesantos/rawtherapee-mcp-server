# HSV Equalizer.SCurve

- section/key: `HSV Equalizer.SCurve`
- autonomous_allowed: `approved_values_only`
- confidence: `medium`
- pending_evidence: `False`
- expected_effect: hue-targeted saturation shaping
- risks: ['oversaturation', 'muted hues if curve shape is too aggressive']

Evidence sources:
- tests/test_pp3_generator.py
- tests/test_control_policy.py
