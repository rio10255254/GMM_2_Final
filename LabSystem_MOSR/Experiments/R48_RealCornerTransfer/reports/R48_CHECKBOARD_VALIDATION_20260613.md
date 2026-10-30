# Lab R48 Checkboard Validation - 2026-06-13

## Verdict

R48 is not yet a pass on this corner check: its best R48 checkpoint
does not beat the strongest previous control on both median corner
shift and the >5 px outlier rate. It should not be promoted without
additional analysis.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 2506
- All R48 GMF case folders must preserve the original 51 BMP filenames.

## Corner Geometry Result

| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 | 1.0x |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 | 93.4x |
| Lab R46 tradeoff | 4.243 | 8.485 | 48.603% | 0.076 | 1.246 | 114.8x |
| Lab R47 latest E200 | 5.000 | 9.220 | 49.441% | 0.100 | 1.083 | 144.2x |
| Lab R48 best_tradeoff | 7.211 | 9.220 | 58.659% | 0.119 | 2.299 | 153.6x |
| Lab R48 best_detail_guarded | 6.708 | 9.220 | 61.453% | 0.128 | 2.910 | 152.7x |
| Lab R48 latest | 7.211 | 9.220 | 61.173% | 0.135 | 3.476 | 157.7x |

## R48 Training Coverage Snapshot

| Package | Total pairs | Ring | Shape | Micro | Boundary | Real texture | Real corner | Lattice intersection | Corner PSF stress | Geometry sidecars |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R48 real-corner training | 6000 | 800 | 700 | 700 | 3000 | 800 | 1600 | 900 | 500 | 6000 |
| R48 held-out real-corner validation | 1200 | 0 | 0 | 0 | 700 | 500 | 300 | 200 | 200 | 1200 |

## Package Verification

| Case | Count | Filename identity | Mean absolute change vs raw |
|---|---:|---|---:|
| raw_input | 51 | True | 0.0000 |
| lab_r40_best_tradeoff | 51 | True | 1.3885 |
| lab_r46_best_tradeoff | 51 | True | 1.6573 |
| lab_r47_latest | 51 | True | 1.6246 |
| lab_r48_best_tradeoff | 51 | True | 1.5940 |
| lab_r48_best_detail_guarded | 51 | True | 1.6560 |
| lab_r48_latest | 51 | True | 1.7358 |

## Interpretation Rule

- Promotion is not allowed from training loss alone.
- The R48 checkpoint must beat the previous real-corner controls on this table.
- External GMF should be interpreted together with this real-corner table.

## Artifacts

- Corner metrics table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r48_20260613/corner_metrics_per_measurement.csv`
- Corner summary table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r48_20260613/corner_metrics_summary.csv`
- Summary JSON: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r48_20260613/corner_validation_summary.json`
- Visual corner sheet: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r48_20260613/corner_patch_contact_sheet.png`
- Metric chart: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r48_20260613/corner_metric_summary.png`
