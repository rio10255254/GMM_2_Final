# Lab R54 Edge-Band Probe Checkboard Validation - 2026-06-16

## Verdict

R54 does not pass the real checkboard corner gate. The edge-band
small-overfit checkpoint does not beat the Lab R40 corner control.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 1790
- All case folders must preserve the original 51 BMP filenames.

## Corner Geometry Result

| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 | 1.0x |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 | 93.4x |
| Lab R53 realistic best | 3.606 | 9.899 | 40.782% | 0.059 | 1.155 | 92.0x |
| Lab R53 realistic latest | 9.220 | 9.899 | 58.939% | 0.075 | 1.140 | 134.7x |
| Lab R54 edge-band epoch20 | 9.220 | 9.220 | 60.056% | 0.080 | 0.834 | 132.7x |

## Pairwise Diagnosis

R54 versus raw input:

| Result | Count |
|---|---:|
| Candidate better | 32 |
| Equal | 40 |
| Candidate worse | 286 |
| Candidate > 5 px while baseline <= 5 px | 210 |
| Candidate <= 5 px while baseline > 5 px | 1 |
| Candidate > 10 px | 34 |
| Baseline > 10 px | 6 |

R54 versus Lab R40 tradeoff:

| Result | Count |
|---|---:|
| Candidate better | 98 |
| Equal | 41 |
| Candidate worse | 219 |
| Candidate > 5 px while baseline <= 5 px | 155 |
| Candidate <= 5 px while baseline > 5 px | 28 |
| Candidate > 10 px | 34 |
| Baseline > 10 px | 17 |

R54 versus R53 best:

| Result | Count |
|---|---:|
| Candidate better | 140 |
| Equal | 51 |
| Candidate worse | 167 |
| Candidate > 5 px while baseline <= 5 px | 130 |
| Candidate <= 5 px while baseline > 5 px | 61 |
| Candidate > 10 px | 34 |
| Baseline > 10 px | 25 |

R54 versus R53 latest:

| Result | Count |
|---|---:|
| Candidate better | 156 |
| Equal | 49 |
| Candidate worse | 153 |
| Candidate > 5 px while baseline <= 5 px | 75 |
| Candidate <= 5 px while baseline > 5 px | 71 |
| Candidate > 10 px | 34 |
| Baseline > 10 px | 25 |

## Package Verification

| Case | Count | Filename identity | Mean absolute change vs raw |
|---|---:|---|---:|
| raw_input | 51 | True | 0.0000 |
| lab_r40_best_tradeoff | 51 | True | 1.3885 |
| lab_r53_realistic_best_tradeoff | 51 | True | 1.4167 |
| lab_r53_realistic_latest | 51 | True | 1.5362 |
| lab_r54_edgeband_epoch020 | 51 | True | 7.2685 |

## Interpretation Rule

- The R54 small-overfit package is allowed to prove local learning ability only.
- A usable real-checkboard result must still beat Lab R40 on real captured corners.
- If R54 improves the masked CAD package but worsens real checkboard corners, the small probe is not a deployable model.

## Artifacts

- Corner metrics table: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/corner_metrics_per_measurement.csv`
- Corner summary table: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/corner_metrics_summary.csv`
- Summary JSON: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/corner_validation_summary.json`
- Visual corner sheet: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/corner_patch_contact_sheet.png`
- Focused corner comparison: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/r54_focus_corner_comparison.png`
- Pairwise comparison JSON: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/r54_pairwise_corner_comparison.json`
- Metric chart: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r54_20260616/corner_metric_summary.png`
