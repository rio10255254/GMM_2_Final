# R116 Coherent Geometry-Anchor Scratch

R116 is the next single-image, tile-native MOSR architecture prepared after
the R109/R112/R113/R114/R115 evidence chain.  It is not an R109 fine-tune and
does not load V42, R61, R109, R114, or R115 weights for formal training.

The architecture keeps the useful R109 contract while changing the part most
likely to disturb external localization:

- boundary coordinates, width, shift, and detail use independent trainable
  towers;
- width and shift are made coherent along the local contour direction rather
  than blurred in two dimensions;
- Raw is first warped into a geometry anchor;
- only bounded, locally zero-mean edge/detail evidence is added to that anchor;
- there is no free image residual, global pooling, global FFT, or spatial
  normalization;
- training may use paired synthetic observations, but deployment still accepts
  one image at a time.

Current state: architecture, data contract, full causal image package, three
independent scratch probes, GPU checks, and locked R73/R74 ACM qualification are
complete.  One full 48-epoch scratch candidate run is authorized.  Model
promotion remains blocked until real-motion and external-GMF validation are
complete.

Formal run 1 stopped safely at epoch 7 when a BF16 probability clamp rounded
to exactly one inside the width-confidence loss.  The failed run is preserved.
All loss reductions now execute in FP32, the original batch-59 failure point
and all 138 width batches pass, and a second independent scratch run is
authorized by `REPAIR_AND_RESTART.json`.

Detailed post-training validation is now complete.  E42 is the primary R116
research candidate and E24 is the secondary geometry/LSC fallback.  E48 is not
selected: it improved some synthetic calibration metrics but regressed the
shared 36-pillar SEM population.  E42 passed all six locked real-motion suites,
all full-frame tile-parity checks, and improved the shared SEM coarse contour
for 36/36 pillars, including most pillars in the darkest exposures.  It still
trails R109/V42 on the thesis LSC readout, regresses two R74 families, and
worsens SEM perimeter fidelity.  The verified 101-frame external-GMF package
is ready, but no external score exists yet.  See
`results/detailed_validation/FINAL_VALIDATION.json`.

Main entry points:

1. `scripts/validate_architecture.ps1`
2. `data/prepare_dataset.py`
3. `training/smoke_train.py`
4. `probes/r109_counterfactuals.py`

The full reasoning and go/no-go sequence are recorded in
`reports/R116_ARCHITECTURE_DECISION_ZH.md`.
