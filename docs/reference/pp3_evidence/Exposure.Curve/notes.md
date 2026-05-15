# Exposure.Curve

- section/key: `Exposure.Curve`
- approved preset id: `tone_curve.midtone_pop_v1`
- paired controls: `Exposure.CurveMode=Standard`, `Exposure.Curve2=0;`
- intended effect: stronger midtone separation and subject depth without opening arbitrary curve authoring
- allowed contexts:
  - `flat_midtone_geometry`
  - `weak_subject_readability`
  - `low_thumbnail_impact`
- avoid contexts:
  - `already_high_contrast`
  - `portrait_skin_fragile`
  - `night_high_iso`
- primary risk: can harden rail/sky transitions if stacked with strong contrast and microcontrast
- evaluation anchor: `docs/evaluations/runs_phase5/IMG_1279/report.json`
