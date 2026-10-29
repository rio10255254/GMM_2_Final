# R61 v1.1 tiled output — external GMF readout

The supplied `GmmVisionTool.exe` was used with the existing Flow and template. No template retraining or external-tool change was made.

## Result

The new tiled R61 sequence produced 100 GMF rows (`r61v11_0001`–`r61v11_0100`). The first image is the sequence reference and has no score row.

| Measure | Raw fixed Flow | R61 v1.1 tiled |
|---|---:|---:|
| GMF score mean | 77.798 | 89.501 |
| GMF score median | 78.558 | 89.485 |
| GMF score spread | 2.348 | 0.199 |
| Y-step mean | -8.021 px | -8.021 px |
| Y-step standard deviation | 8.194 px | 0.413 px |
| Mean absolute Y-step error | 6.502 px | 0.341 px |
| Correct negative-Y direction | 86.0% | 100.0% |
| Y-line residual spread | 5.469 px | 0.304 px |

All 100 R61 scores were above the GMF acceptance value of 59. Every paired R61 score was higher than Raw; the median gain was 10.93 points and the mean gain was 11.69 points.

## Coordinate interpretation

R61 has a mostly fixed absolute coordinate offset from Raw: median `+27.65 px` in X and `+11.70 px` in Y. The offset changes only about `-0.030 px/frame` in X and `-0.007 px/frame` in Y. This is a calibration offset, not a loss of displacement stability. For relative motion measurement, subtract the first coordinate or calibrate the fixed offset; for absolute coordinates, retain this offset in the calibration record.

The fitted Y slope is `-8.0194 px/step`, essentially matching the commanded `-8 px/step` and the historical R61 external-GMF result.

## Files

- Source score log: `E:/Archive/GMM_Software_residual/GmmVisionToolExe_20260107/GMF_score.txt`
- New tiled images: `Thesis_MOSR_Evidence/External_GMF_Packages/GmmVisionTool_FixedFlow_Benchmark/r61v11_tiled_unique`
- Machine-readable readout: `analysis/r61v11_gmf_analysis.json`
