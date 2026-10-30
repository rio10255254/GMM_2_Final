# R55 Checkboard Validation

## Scope

- Frames checked: 51
- Raw checker corners accepted by detector: 358
- Same real Lab 20250605 checkboard sequence as R53/R54 validation.

## Corner Geometry Summary

| Case | Median shift px | Tail shift px | Corners > 5 px | Median local change vs raw | Median edge strength |
|---|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 |
| Lab R51 mixed-PSF best | 2.828 | 9.220 | 36.872% | 0.057 | 1.210 |
| Lab R52 latest | 3.606 | 8.485 | 30.447% | 0.095 | 1.098 |
| Lab R53 best | 3.606 | 9.899 | 40.782% | 0.059 | 1.155 |
| Lab R53 latest | 9.220 | 9.899 | 58.939% | 0.075 | 1.140 |
| Lab R55 best | 2.828 | 3.606 | 21.788% | 0.050 | 1.322 |
| Lab R55 latest | 8.485 | 9.220 | 51.397% | 0.061 | 1.192 |

## Guard Result

| Candidate | Control | Pass | Failed rules |
|---|---|---:|---|
| lab_r55_source_style_best_tradeoff | lab_r40_best_tradeoff | True | none |
| lab_r55_source_style_latest | lab_r40_best_tradeoff | False | median_not_better, large_shift_rate_worse, tail_worse |

## Pairwise Delta

| Candidate | Baseline | Better corners | Median delta px | Mean delta px |
|---|---|---:|---:|---:|
| lab_r55_source_style_best_tradeoff | lab_r40_best_tradeoff | 59.5% | -0.637 | -0.420 |
| lab_r55_source_style_latest | lab_r40_best_tradeoff | 32.7% | 0.414 | 1.522 |
| lab_r55_source_style_best_tradeoff | lab_r53_realistic_best_tradeoff | 54.2% | -0.592 | -1.518 |
| lab_r55_source_style_latest | lab_r53_realistic_latest | 45.0% | 0.000 | -0.781 |
| lab_r55_source_style_best_tradeoff | lab_r52_stability_latest | 63.1% | -0.777 | -1.114 |

## Package Check

| Case | BMP count | Filenames match raw | Mean abs change vs raw |
|---|---:|---:|---:|
| raw_input | 51 | True | 0.000 |
| lab_r40_best_tradeoff | 51 | True | 1.389 |
| lab_r51_mixed_psf_best_tradeoff | 51 | True | 1.408 |
| lab_r52_stability_latest | 51 | True | 1.631 |
| lab_r53_realistic_best_tradeoff | 51 | True | 1.417 |
| lab_r53_realistic_latest | 51 | True | 1.536 |
| lab_r55_source_style_best_tradeoff | 51 | True | 1.865 |
| lab_r55_source_style_latest | 51 | True | 2.514 |

## Interpretation

- R55 is judged only after this real-checkboard validation, not by internal training PSNR alone.
- The selected Lab candidate must improve the median corner response and must not increase the large-shift tail against the Lab R40 control.
- The training log already warned about oversmoothing, so the latest checkpoint is especially suspicious until the real-corner numbers prove otherwise.

## Artifacts

- Per-corner table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r55_20260618/corner_metrics_per_measurement.csv`
- Summary table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r55_20260618/corner_metrics_summary.csv`
- Package check: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r55_20260618/r55_gmf_package_check.json`
- Guard JSON: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r55_20260618/r55_corner_gate.json`
- Visual corner sheet: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r55_20260618/corner_patch_contact_sheet.png`
- Metric chart: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r55_20260618/corner_metric_summary.png`
