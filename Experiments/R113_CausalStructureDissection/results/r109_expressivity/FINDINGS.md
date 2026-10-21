# R109 Renderer Expressivity Upper Bound

This is a deterministic no-training representation test. Oracle controls see target truth; they are not deployment results.

- Scenes: 24 (8 shape families; bright and dark polarity; supersampled labels)
- Learned R109 median ASSD: 0.0930 px
- Dense truth-optimized median / worst ASSD: 0.0058 / 3.2401 px
- Smooth truth-optimized median / worst ASSD: 0.0238 / 9.1657 px
- Learned-to-dense median ASSD improvement: 93.72%
- Smooth-to-bounded-detail HF RMSE improvement: 37.83%
- Dense-oracle hard cases (ASSD > 1 px or IoU < .92): 3/24
- Smooth-control same-shape condition ASSD: 0.9215 px
- Smooth-control shape retention ratio: 1.0046
- Primary limit: renderer_capacity_primary_for_hard_cases_controls_secondary
- Go / no-go: NO-GO for control-only retraining: the current renderer still fails known-truth hard cases even with dense oracle controls; test a bounded detail/geometry extension first.

## Interpretation

- Learned controls: A material learned-to-oracle gap means current training/control prediction leaves usable renderer capacity untapped.
- Renderer: The dense truth-optimized renderer still has hard cases, so width/normal-shift remapping is not universally expressive.
- Detail path: A bounded zero-local-mean detail path closes a material high-frequency gap without changing the renderer controls.

External GMF is deliberately absent. This experiment asks what the renderer can physically express against known truth.
