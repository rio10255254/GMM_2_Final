# R72 frozen manifest

## Scientific question

Does the frozen R61v16 reconstruction make the complete non-circular contour of unseen synthetic microscopy edge defects closer to the clean paired truth than the raw optical-like input?

## Why this is an ACM-valid subset

The primary population is the twenty held-out `edge_defects` images from R71. Each image contains one closed, deliberately jagged specimen body with local notches, spots, and scratches. This provides one unambiguous full outer contour per image. The other R71 families contain open grids, stochastic textures, or several overlapping objects, so a single ACM outline would not represent a consistent physical object; they remain covered by the broader R71 image-level tests but are excluded from the primary ACM claim.

## Frozen contour protocol

- MATLAB `activecontour`, Chan-Vese, 200 iterations, smooth factor 1.0, contraction bias 0.
- Every truth, Raw, COMBO, and R61 image uses the same fixed outer rectangle as initialization. The rectangle starts outside the known nominal specimen envelope and does not use the per-image clean contour.
- Intensity is normalized before ACM using the same procedure as R69/R70. Brightness and contrast are therefore inputs to finding the contour, but all reported agreement measures are computed only from the resulting binary shapes.
- Primary comparison translates each predicted mask to the truth centroid, matching the R69/R70 shape-only protocol. No scale or rotation fitting is allowed.
- A secondary fixed-coordinate comparison keeps position error instead of translating it away.
- Measures: IoU, Dice, mean symmetric boundary distance, boundary HD95, area error, perimeter error, and circularity error. No circle or radius is fitted.
- Robustness: three fixed smoothness/iteration settings are rerun on six preselected image IDs spanning the held-out index range.

## Statistical unit and decision gate

The independent unit is the independently generated image, n=20. The coarse full-contour gate requires both IoU and mean boundary distance to improve on at least 60% of images and to have a positive fixed-seed bootstrap lower bound. All three ACM presets must preserve positive median improvement for both measures. Perimeter and circularity are reported as fine-shape checks and do not replace the coarse-contour gate.

## Interpretation boundary

This is a strict, paired synthetic shape test with known truth. It tests one closed jagged defect family. It does not prove universal performance on open lines, textures, multi-object fields, real SEM samples, or all brightness regimes.
