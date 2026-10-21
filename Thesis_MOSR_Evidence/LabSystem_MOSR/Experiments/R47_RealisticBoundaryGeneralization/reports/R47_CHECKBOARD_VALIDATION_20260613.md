# Lab R47 Checkboard Validation - 2026-06-13

## Verdict

R47 was reconstructed on the real 20250605 Lab checkboard sequence and
compared against raw input plus the earlier R40/R46 controls using the
same corner-response validation method as the R46 report.

The result is negative: neither R47 checkpoint solves the real checkboard
corner problem. R47 best_tradeoff is worse than the earlier R40/R46 controls,
and R47 latest is less bad than R47 best_tradeoff but still worse than R40
tradeoff and R46 tradeoff on this corner metric.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 1790
- All R47 GMF case folders preserve the original 51 BMP filenames.

## Corner Geometry Result

| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 | 1.0x |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 | 93.4x |
| Lab R46 tradeoff | 4.243 | 8.485 | 48.603% | 0.076 | 1.246 | 114.8x |
| Lab R47 best_tradeoff E33 | 7.211 | 9.220 | 75.419% | 0.099 | 1.090 | 119.7x |
| Lab R47 latest E200 | 5.000 | 9.220 | 49.441% | 0.100 | 1.083 | 144.2x |

## R47 Training Coverage Snapshot

| Package | Total pairs | Ring | Shape | Micro | Boundary | Real background | Checkboard corner | Intersection edge | Real background boundary | PSF stress |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R47 realistic boundary training | 4000 | 700 | 700 | 700 | 1200 | 700 | 600 | 400 | 700 | 200 |
| R47 held-out realistic boundary validation | 800 | 0 | 0 | 0 | 600 | 200 | 200 | 200 | 200 | 200 |

## Package Verification

| Case | Count | Filename identity | Mean absolute change vs raw |
|---|---:|---|---:|
| raw_input | 51 | True | 0.0000 |
| lab_r47_best_tradeoff | 51 | True | 1.5065 |
| lab_r47_latest | 51 | True | 1.6246 |

## External GMF Status

The R47 case folders are prepared under `gmf_cases/`, but no
`GMF_score.txt` files were present at report generation time. External
GMF remains pending and should not override this corner-geometry failure
unless the returned score is interpreted together with the corner table.

## Interpretation

- Raw input remains the best geometry reference by median corner shift.
- R47 latest is the better of the two R47 checkpoints, but it still does not beat the earlier R40/R46 controls.
- R47 best_tradeoff is safer by training selection, but it is worse on this real corner metric.
- Both R47 checkpoints are packaged for external GMF, but GMF should be interpreted together with this corner check.

## Artifacts

- Corner metrics table: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\corner_geometry_validation_r47_20260613\corner_metrics_per_measurement.csv`
- Corner summary table: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\corner_geometry_validation_r47_20260613\corner_metrics_summary.csv`
- Summary JSON: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\corner_geometry_validation_r47_20260613\corner_validation_summary.json`
- Visual corner sheet: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\corner_geometry_validation_r47_20260613\corner_patch_contact_sheet.png`
- Metric chart: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\corner_geometry_validation_r47_20260613\corner_metric_summary.png`
