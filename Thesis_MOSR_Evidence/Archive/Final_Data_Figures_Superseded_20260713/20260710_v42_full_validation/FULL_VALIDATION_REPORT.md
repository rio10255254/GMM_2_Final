# V42 Epoch 120 Comprehensive Validation

Primary displacement rule: Raw, V41, and V42 use identical frame pairs and frozen-V41 shared edge positions. Three ROIs are reported per dataset, and search-boundary saturation is rejected. No sample-specific scale correction is used.

## 1. Traceable 100MG CD

| Feature | Raw MAE (nm) | V41 MAE (nm) | V42 E120 MAE (nm) | V42 improvement vs Raw | Per-feature improved |
|---|---:|---:|---:|---:|---:|
| pillar | 81.26 | 64.60 | 66.56 | +18.09% | 36/36 |
| via | 314.11 | 243.14 | 260.61 | +17.03% | 35/36 |

V42 improves nearly every individual feature versus Raw, but V41 remains better on the mean CD error.

## 2. Real displacement, three-ROI sensitivity revalidation

Common-best-30 selection is case symmetric: the same frame pairs are used for Raw, V41, and V42. The primary metric combines step RMSE to commanded motion with boundary-localization uncertainty, preventing a stable but biased result from appearing artificially strong.

| Sequence | Error-aware status | Minimum improvement | Median improvement | Maximum improvement | Step-SD status |
|---|---|---:|---:|---:|---|
| x_1um | robust_improvement | +10.58% | +53.08% | +55.37% | roi_sensitive |
| x_0p5um | incomplete | +49.11% | +54.96% | +60.81% | incomplete |
| 20x_1um | robust_improvement | +30.86% | +47.66% | +50.14% | robust_degradation |
| 20x_0p5um | roi_sensitive | -50.75% | +52.99% | +57.92% | roi_sensitive |
| 5x_1um | robust_improvement | +2.80% | +27.25% | +29.51% | robust_degradation |
| 5x_0p5um | robust_improvement | +2.73% | +29.75% | +30.77% | roi_sensitive |

Across the six sequences, 4 are robust improvements across all three ROIs, 1 is ROI-sensitive, and 1 is incomplete because one ROI fails the detector validity gate. Step-SD results are reported separately because edge reconstruction cannot make the physical stage itself more stable.

The previous single-ROI result is retained only as an audit. Exact ROI overlays, edge locations, step traces, and per-ROI tables are in roi_sensitivity_revalidation.

## 3. Held-out synthetic shapes

- Mean boundary distance: Raw 0.1711 px; V42 0.3231 px.
- V42 improves 6/20 images.
- Symmetric Gaussian blur preserves its half-height boundary, so this test mainly acts as a no-harm/generalization check. V42 does not pass that check on these out-of-domain shapes.

## 4. Unseen concentric-circle captures

- Complete-circle frames: 10 selected by Raw visibility from the first 50 captures.
- Radius standard deviation: Raw 0.07250 px; V42 0.07303 px.
- Mean radial RMS residual: Raw 0.32790 px; V42 0.36296 px.
- V42 is essentially tied on radius repeatability and slightly worse on roundness residual.

## Overall conclusion

V42 E120 gives traceable 100MG CD improvement and usually produces steeper, easier-to-localize boundaries. The three-ROI revalidation shows that this advantage is robust in four displacement sequences, ROI-sensitive in 20x 0.5 um/step, and incomplete in 50x 0.5 um/step. It does not consistently reduce physical step-to-step variation, synthetic out-of-domain error, or concentric-circle roundness residual. The defensible conclusion is target-domain boundary-localization improvement, not universal displacement-stability superiority.
