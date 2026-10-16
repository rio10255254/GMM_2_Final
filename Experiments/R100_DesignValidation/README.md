# R100 Design Validation

This is an analysis-only preflight. It does not define an R100 model and it
cannot launch training.

The validation answers four questions before the next architecture is fixed:

1. Does the geometry supervision become exactly zero when source and target
   geometry are already aligned?
2. Can a symmetric, source-supported detail operator improve fine structure
   without moving contours or destabilising displacement?
3. Do the same conclusions survive synthetic truth, 5x/20x/50x real images,
   exact tiling, and the real x_1um sequence?
4. Is Chan-Vese ACM stable enough under geometry-preserving photometric changes
   to be used as the sole checkpoint-selection signal?

Run `scripts\Run_Validation.ps1`. All generated files stay under `results` and
`reports`; the large source datasets are referenced read-only.

