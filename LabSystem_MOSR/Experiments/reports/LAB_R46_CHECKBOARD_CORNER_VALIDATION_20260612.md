# Lab R46 Checkboard Corner Geometry Validation - 2026-06-12

## Question

Does the LabSystem reconstruction preserve real checkboard corners, or does it reshape hard right angles in a way that can explain the weak GMF improvement?

## Completion Criteria

- Check more than one frame and more than one corner.
- Compare raw input with R39/R40 latest and tradeoff outputs plus the first R46 candidates.
- Separate corner-geometry evidence from the external GMF score.
- Audit whether the current Lab training packages contain direct checkboard/corner coverage.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 2864
- Corner detector: raw-image Harris/good-features points filtered for checker-like diagonal contrast.
- Geometry check: compare where the strongest corner response lands inside the same local patch.

## Corner Geometry Result

| Case | Median corner-response shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 1.414 | 2.236 | 1.676% | 0.000 | 1.049 | 1.0x |
| Lab R39 latest | 3.606 | 9.899 | 47.765% | 0.058 | 1.209 | 80.6x |
| Lab R40 latest | 3.606 | 9.220 | 38.268% | 0.066 | 1.298 | 101.9x |
| Lab R39 tradeoff | 9.220 | 10.630 | 52.514% | 0.071 | 1.307 | 74.9x |
| Lab R40 tradeoff | 4.243 | 5.000 | 24.581% | 0.068 | 1.361 | 93.4x |
| Lab R46 tradeoff | 4.243 | 8.485 | 48.603% | 0.076 | 1.246 | 114.8x |
| Lab R46 detail | 4.243 | 8.485 | 46.089% | 0.078 | 1.259 | 115.1x |
| Lab R46 latest | 5.831 | 7.211 | 52.793% | 0.082 | 1.247 | 112.2x |

Interpretation:

- The reconstruction outputs do not merely blur or sharpen the raw image. The key question is whether they move the strongest local corner response away from the raw corner location.
- R46 should be judged against both the raw input and the earlier R39/R40 cases. A useful R46 candidate should reduce the corner-response shift without creating a larger local change from raw.
- In this run, R46 tradeoff and R46 detail tie R40 tradeoff on median shift, but they have many more corners above 5 px shift and a larger local change from raw. R46 latest is worse.
- Stronger-looking edges are not enough. The preferred model must preserve square-corner geometry on this real checkboard sequence.

## Training Coverage Audit

| Package | Total pairs | Rectangle pairs | Rectangle share | Micro-grid pairs | Micro-grid share | Checkboard-specific pairs |
|---|---:|---:|---:|---:|---:|---:|
| R39 safe training | 1240 | 20 | 1.613% | 0 | 0.000% | 0 |
| R39 strong package | 1590 | 70 | 4.403% | 0 | 0.000% | 0 |
| R39 shape validation | 210 | 30 | 14.286% | 0 | 0.000% | 0 |
| R40 training | 1300 | 50 | 3.846% | 80 | 6.154% | 0 |
| R40 microscopy validation | 100 | 0 | 0.000% | 20 | 20.000% | 0 |
| R46 corner-aware training | 1550 | 50 | 3.226% | 50 | 3.226% | 400 |
| R46 held-out corner validation | 100 | 0 | 0.000% | 0 | 0.000% | 100 |
| Training_Data keyword audit | 56 | 0 | 0.000% | 0 | 0.000% | 56 |

Coverage interpretation:

- R39 safe training uses only 20 rectangle pairs out of 1240 pairs.
- R40 training uses 50 rectangle pairs and 80 micro-grid pairs out of 1300 pairs.
- R46 training adds 400 synthetic checkboard/corner pairs out of 1550 pairs.
- R46 held-out validation adds 100 synthetic checkboard/corner pairs.
- Training_Data keyword audit found 56 checker/checkboard/chessboard-specific paths.
- The new R46 validation set is still synthetic. It is not a real captured Lab checkboard-corner validation set.

## Root-Cause Assessment

High confidence: the weak checkboard result is not explained only by the shared abnormal displacement interval.

The stronger explanation is a remaining target-domain mismatch:

- R46 was explicitly trained on synthetic checkboard/corner data, but that did not transfer cleanly to the real Lab checkboard capture.
- The model learned to create stronger-looking edges, but not to preserve the exact square-corner geometry needed by this sample.
- The checkpoint choice can therefore look acceptable on synthetic validation while still damaging real captured checkboard corners.

Medium confidence: the Lab PSF may contribute to the artifact, because an imperfect blur model can teach the model the wrong edge compensation.

Lower confidence: a basic inference/package mistake, because all cases have matching filenames and frame counts and the distortion repeats systematically.

## Recommended Next Evidence

1. Do not treat this R46 run as solving the rounded-corner problem.
2. If an external GMF check is still desired, send R46 tradeoff first because it is the least-bad R46 candidate here.
3. Keep raw input as the reference case and keep R39/R40 as historical controls.
4. Revise the corner/checkboard training package before longer training.

## Generated Files

- Corner metrics table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r46_20260612/corner_metrics_per_measurement.csv`
- Corner summary table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r46_20260612/corner_metrics_summary.csv`
- Training coverage table: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r46_20260612/training_data_coverage_summary.csv`
- Visual corner sheet: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r46_20260612/corner_patch_contact_sheet.png`
- Metric chart: `LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r46_20260612/corner_metric_summary.png`
