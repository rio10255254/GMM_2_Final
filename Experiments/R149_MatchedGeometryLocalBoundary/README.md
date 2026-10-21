# R149 — Matched Geometry + Local Boundary

## Hypothesis

R148v2 proved that the one-pass context branch and three native stages improve repeatability, but its synthetic dense geometry did not cover the real nine-circle spacing and its global boundary statistics allowed opposite local size errors to cancel. R149 keeps the complete R148v2 architecture and changes only the training evidence and boundary objective needed to test that diagnosis.

## Design

- Keep the R148v2 one-pass context U-Net and three independent native-grid stages unchanged.
- Replace a deterministic subset of dense parents with procedural circle grids at radius 6–12 px and pitch 24–36 px: 64 train, 16 dev, 16 test.
- Preserve the remaining dense stress scenes and all other scene families.
- Form blur with the same measured 25-PSF bank, but give the model only the fixed mean PSF during both training and inference.
- Use an 8×8 local-cell boundary statistic so opposite sides and nearby circles cannot cancel as one image-wide average. The boundary weight is 0.35 after the first 0.20/75%-local pilot improved the common local score by only 0.75% and failed the preset 3% gate.
- Use procedural geometry only. Real images, SEM diameters and PI measurements are excluded from training answers.

## Formal gate

Two fresh seeds compare the old global-boundary objective with the new local objective for 512 updates on the same R149 data. The formal run starts only if the local objective improves the common matched-circle local-boundary score by at least 3%, keeps matched-circle image error within 5%, and preserves sub-0.001 px translation consistency.

## Status

Implementation and data preparation are in progress. Completion requires the gated 8,192-update scratch run and the unchanged 930-frame real validation. Training completion does not promote a formal baseline.

## Branch

`sandbox/r149-matched-geometry-local-boundary`

## Final verdict

The local-boundary arm failed the fixed 3% matched-circle gate twice (0.75% and 0.81%) and did not enter formal training. The failure receipts and all six short controls are preserved. Follow-up formal work moves to R150 and retains only the supported matched-geometry and mean-PSF interventions.

