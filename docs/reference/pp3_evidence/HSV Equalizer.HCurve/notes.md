# HSV Equalizer.HCurve

- section/key: `HSV Equalizer.HCurve`
- autonomous_allowed: `False`
- confidence: `high`
- pending_evidence: `False`
- expected_effect: hue remapping
- risks: ['broad color drift', 'cyan/warm split', 'unintended global hue remap']

Evidence sources:
- src/rawtherapee_mcp/pp3_generator.py
- tests/test_control_policy.py
