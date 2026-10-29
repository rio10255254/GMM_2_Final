# Lab R53 Realistic Dataset Calibration Checkboard Validation - 2026-06-16

## Verdict

R53 improves the median corner shift but still raises the large-shift
corner rate. Treat it as directional evidence, not a pass.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 2148
- All case folders must preserve the original 51 BMP filenames.

## Corner Geometry Result

| Case | Median corner shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 | 1.0x |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 | 93.4x |
| Lab R51 mixed-PSF best | 2.828 | 9.220 | 36.872% | 0.057 | 1.210 | 89.5x |
| Lab R52 stability latest | 3.606 | 8.485 | 30.447% | 0.095 | 1.098 | 151.4x |
| Lab R53 realistic best | 3.606 | 9.899 | 40.782% | 0.059 | 1.155 | 92.0x |
| Lab R53 realistic latest | 9.220 | 9.899 | 58.939% | 0.075 | 1.140 | 134.7x |

## Pairwise Diagnosis

R53 latest versus Lab R40 tradeoff:

| Result | Count |
|---|---:|
| Candidate better | 96 |
| Equal | 25 |
| Candidate worse | 237 |
| Candidate > 5 px while baseline <= 5 px | 155 |
| Candidate <= 5 px while baseline > 5 px | 32 |
| Candidate > 10 px | 25 |
| Baseline > 10 px | 17 |

R53 latest versus Lab R51 mixed-PSF best:

| Result | Count |
|---|---:|
| Candidate better | 90 |
| Equal | 94 |
| Candidate worse | 174 |
| Candidate > 5 px while baseline <= 5 px | 106 |
| Candidate <= 5 px while baseline > 5 px | 27 |
| Candidate > 10 px | 25 |
| Baseline > 10 px | 39 |

R53 latest versus Lab R52 latest:

| Result | Count |
|---|---:|
| Candidate better | 115 |
| Equal | 34 |
| Candidate worse | 209 |
| Candidate > 5 px while baseline <= 5 px | 135 |
| Candidate <= 5 px while baseline > 5 px | 33 |
| Candidate > 10 px | 25 |
| Baseline > 10 px | 28 |

R53 best versus Lab R40 tradeoff:

| Result | Count |
|---|---:|
| Candidate better | 128 |
| Equal | 65 |
| Candidate worse | 165 |
| Candidate > 5 px while baseline <= 5 px | 99 |
| Candidate <= 5 px while baseline > 5 px | 41 |
| Candidate > 10 px | 25 |
| Baseline > 10 px | 17 |

## R53 Training Coverage Snapshot

| Package | Total pairs | Ring | Shape | Micro | Corner | Boundary | Real BG | CAD anchor | Formal BADS corner | Gaussian corner | Weak-BADS 0.50 corner |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R53 realistic 6000-pair training | 6000 | 700 | 700 | 900 | 300 | 2050 | 950 | 400 | 100 | 100 | 100 |
| R53 held-out realistic validation | 1740 | 0 | 0 | 0 | 120 | 1100 | 400 | 120 | 40 | 40 | 40 |

## Package Verification

| Case | Count | Filename identity | Mean absolute change vs raw |
|---|---:|---|---:|
| raw_input | 51 | True | 0.0000 |
| lab_r40_best_tradeoff | 51 | True | 1.3885 |
| lab_r51_mixed_psf_best_tradeoff | 51 | True | 1.4077 |
| lab_r52_stability_latest | 51 | True | 1.6313 |
| lab_r53_realistic_best_tradeoff | 51 | True | 1.4167 |
| lab_r53_realistic_latest | 51 | True | 1.5362 |

## Interpretation Rule

- R53 is a formal Lab realistic-data round, but promotion still depends on real image evidence.
- A promoted result must beat Lab R40 tradeoff on real checkboard corners without increasing large corner errors.
- The final checkpoint must be checked separately because internal validation kept improving after the best-checkpoint window closed.

## Artifacts

- Corner metrics table: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/corner_metrics_per_measurement.csv`
- Corner summary table: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/corner_metrics_summary.csv`
- Summary JSON: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/corner_validation_summary.json`
- Visual corner sheet: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/corner_patch_contact_sheet.png`
- Focused corner comparison: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/r53_focus_corner_comparison.png`
- Pairwise comparison JSON: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/r53_pairwise_corner_comparison.json`
- Metric chart: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r53_20260616/corner_metric_summary.png`
