# Luminance Curve.AvoidColorShift

- section/key: `Luminance Curve.AvoidColorShift`
- autonomous_allowed: `True`
- confidence: `low`
- pending_evidence: `True`
- expected_effect: mitigates chroma drift while adjusting luminance curve
- risks: ['unexpected desaturation if combined with heavy curve edits']

Evidence sources:
- tests/test_pp3_generator.py
- docs/reference/pp3_evidence/Luminance Curve.AvoidColorShift/diff.json
- docs/reference/pp3_evidence/Luminance Curve.AvoidColorShift/notes.md
