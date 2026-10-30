# Lab R51 Blur-Source Probe Checkboard Validation - 2026-06-14

## Verdict

R51 improves the median corner shift but still raises the large-shift
corner rate. Treat it as directional evidence, not a pass.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 4296
- All case folders must preserve the original 51 BMP filenames.

## Corner Geometry Result

| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 | 1.0x |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 | 93.4x |
| Lab R46 tradeoff | 4.243 | 8.485 | 48.603% | 0.076 | 1.246 | 114.8x |
| Lab R47 latest E200 | 5.000 | 9.220 | 49.441% | 0.100 | 1.083 | 144.2x |
| Lab R48 best_detail_guarded | 6.708 | 9.220 | 61.453% | 0.128 | 2.910 | 152.7x |
| Lab R49 latest E100 | 9.000 | 9.055 | 85.475% | 0.070 | 1.095 | 3.0x |
| Lab R51 Gaussian best | 3.606 | 9.220 | 37.989% | 0.067 | 1.262 | 104.3x |
| Lab R51 Gaussian latest | 3.606 | 9.220 | 41.061% | 0.068 | 1.272 | 104.4x |
| Lab R51 weak-BADS best | 3.606 | 9.220 | 37.151% | 0.062 | 1.283 | 101.5x |
| Lab R51 weak-BADS latest | 9.220 | 9.899 | 54.469% | 0.054 | 1.229 | 83.0x |
| Lab R51 mixed-PSF best | 2.828 | 9.220 | 36.872% | 0.057 | 1.210 | 89.5x |
| Lab R51 mixed-PSF latest | 2.828 | 9.899 | 41.620% | 0.056 | 1.213 | 86.6x |

## R51 Training Coverage Snapshot

| Package | Total pairs | Ring | Shape | Micro | Corner | Formal BADS corner | Gaussian corner | Weak-BADS 0.50 corner |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R51 Gaussian probe | 1550 | 550 | 350 | 250 | 400 | 0 | 400 | 0 |
| R51 weak-BADS probe | 1550 | 550 | 350 | 250 | 400 | 0 | 0 | 400 |
| R51 mixed-PSF probe | 1550 | 550 | 350 | 250 | 400 | 134 | 133 | 133 |
| R51 held-out mixed corner validation | 100 | 0 | 0 | 0 | 100 | 34 | 33 | 33 |

## Package Verification

| Case | Count | Filename identity | Mean absolute change vs raw |
|---|---:|---|---:|
| raw_input | 51 | True | 0.0000 |
| lab_r40_best_tradeoff | 51 | True | 1.3885 |
| lab_r46_best_tradeoff | 51 | True | 1.6573 |
| lab_r47_latest | 51 | True | 1.6246 |
| lab_r48_best_detail_guarded | 51 | True | 1.6560 |
| lab_r49_latest | 51 | True | 5.9453 |
| lab_r51_gaussian_best_tradeoff | 51 | True | 1.3929 |
| lab_r51_gaussian_latest | 51 | True | 1.9820 |
| lab_r51_weak_bads_best_tradeoff | 51 | True | 1.4817 |
| lab_r51_weak_bads_latest | 51 | True | 1.6686 |
| lab_r51_mixed_psf_best_tradeoff | 51 | True | 1.4077 |
| lab_r51_mixed_psf_latest | 51 | True | 1.5898 |

## Interpretation Rule

- R51 is a blur-source probe, not a formal Lab model promotion round.
- A useful result must beat Lab R40 tradeoff on real checkboard corners.
- Training loss and synthetic validation are secondary to the real corner table.

## Artifacts

- Corner metrics table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/corner_metrics_per_measurement.csv`
- Corner summary table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/corner_metrics_summary.csv`
- Summary JSON: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/corner_validation_summary.json`
- Visual corner sheet: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/corner_patch_contact_sheet.png`
- Metric chart: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/corner_metric_summary.png`
