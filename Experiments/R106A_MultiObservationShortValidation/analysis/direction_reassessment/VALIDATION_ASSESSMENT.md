# Validation Report

## Overall Assessment: Share with caveats

The evidence is strong enough to decide that the current R106 design should not receive a full training run and that multi-observation reconstruction should not remain the universal MOSR mainline. The evidence is not sufficient to claim that real JunHua N=4 is more or less accurate than N=2 because no independent real boundary truth or external-GMF result exists for R106A.

## Methodology Review

- Direct N=1/N=2/N=4 claims use one locked R106A checkpoint and one 144-image held-out population.
- Real JunHua comparisons use one locked checkpoint and 100 registered adjacent-position bundles.
- R105B versus R106A and R61 external GMF versus R106A proxies are explicitly treated as directional context, not direct A/B comparisons.
- Completed JSON artifacts and manifests were re-read; expected completion states and row counts were asserted before calculations.

## Issues Found

1. **High:** Real N=4 has no independent SEM, calibrated stage truth, or external-GMF result. Ring-center and edge proxies establish safety, not accuracy gain.
2. **Medium:** R105B and R106A differ in architecture, nuisance access, training distribution and application interface. Their result difference cannot identify one causal code change.
3. **Medium:** R61 external GMF is a different measurement surface from R106A internal geometry. It supports product prioritization but not geometric equivalence.
4. **Low:** Portable HTML enhanced-reader QA encountered a fallback horizontal-overflow defect. The same canonical artifact passed MCP validation and rendered successfully in the native report surface.

## Calculation Spot-Checks

- N=2 contour improvement versus N=1: verified at 8.09%.
- N=4 contour regression versus N=2: verified at 3.62%.
- N=4 exposure-spread increase versus N=1: verified at 99.46%.
- JunHua two-position fractional phase separation: verified at 0.161 px median across 100 steps.
- Phase separation versus real N=4 output change: verified as weak negative Spearman association (-0.121).
- R61 external fixed-flow Y-step SD: verified at 0.413 px from the completed external analysis.

## Required Caveats

- The recommendation is about research priority and product fit, not a claim that multi-frame reconstruction is impossible.
- Same-position N=2 remains potentially useful for noise and stability.
- A deliberate-dither capture or non-learned information-ceiling experiment could reopen the high-resolution multi-frame branch.
