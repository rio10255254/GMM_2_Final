# R150 — Matched Geometry + Mean PSF

## Hypothesis

R148v2 achieved the best diameter repeatability but remained systematically oversized. Its training set lacked the real nine-circle spacing, and 25% of training views supplied an individual PSF identity that is unavailable at inference. R150 tests the two supported corrections while leaving the successful architecture and boundary objective unchanged.

## Design

- Reuse the complete R148v2 one-pass context U-Net plus three independent native stages.
- Reuse the locked R149 combined data: 64/16/16 dense parents were replaced by procedural circle grids at radius 6–12 px and pitch 24–36 px; all other parents remain unchanged.
- Use all 25 measured PSFs to form varied blur, but give the model the fixed mean PSF for every training and inference frame.
- Retain the R148v2 global boundary objective. The attempted local-boundary follow-up is preserved in R149 and was excluded after two versions missed the preset 3% gate.
- Use no real images, SEM sizes or PI positions as training answers.

## Evidence gate

Two R149 controls with this exact data, mean-PSF policy and global boundary objective completed 512 updates from independent initializations and reduced fixed dev error from 8.016 to 5.419/5.466. R150 additionally requires its own 64-update artifact-identity smoke run and architecture/data checks before source freeze.

## Status

The one 8,192-update scratch run and the fixed 930-frame/8,370-circle real validation completed with final audit pass. Generated test improved 6.45% overall versus frozen R148v2. In real data, short-step MAE was 3.876 nm and de-sized shape repeatability was 16.483 nm, but diameter repeatability worsened to 22.389 nm and same-sample SEM mean diameter error increased to 220.324 nm. R150 is retained as a research trade-off and is not promoted. See [training results](reports/R150_RESULTS.md) and [complete real validation](reports/R150_REAL_VALIDATION_RESULTS.md).

## Branch

`sandbox/r150-matched-geometry-mean-psf`
