# Lab Checkboard Corner Geometry Validation - 2026-06-11

## Question

Does the LabSystem reconstruction preserve real checkboard corners, or does it reshape hard right angles in a way that can explain the weak GMF improvement?

## Completion Criteria

- Check more than one frame and more than one corner.
- Compare raw input with R39/R40 latest and tradeoff outputs.
- Separate corner-geometry evidence from the external GMF score.
- Audit whether the current Lab training packages contain direct checkboard/corner coverage.

## Image Evidence Scope

- Frames checked: 51
- Raw checker corners accepted by the detector: 358
- Case measurements: 1790
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

Interpretation:

- The reconstruction outputs do not merely blur or sharpen the raw image. They move the strongest local corner response away from the raw corner location.
- R40 latest and R39 tradeoff show the largest median corner-response shift in this run. R39 latest and R40 tradeoff are less severe but still shifted relative to raw.
- All reconstructed cases show much stronger local corner/edge response than raw, which matches the visual pattern: hard-looking edges plus changed corner geometry.
- This is consistent with the user's observation that right-angle corners are being reshaped instead of faithfully preserved.

## Training Coverage Audit

| Package | Total pairs | Rectangle pairs | Rectangle share | Micro-grid pairs | Micro-grid share | Checkboard-specific pairs |
|---|---:|---:|---:|---:|---:|---:|
| R39 safe training | 1240 | 20 | 1.613% | 0 | 0.000% | 0 |
| R39 strong package | 1590 | 70 | 4.403% | 0 | 0.000% | 0 |
| R39 shape validation | 210 | 30 | 14.286% | 0 | 0.000% | 0 |
| R40 training | 1300 | 50 | 3.846% | 80 | 6.154% | 0 |
| R40 microscopy validation | 100 | 0 | 0.000% | 20 | 20.000% | 0 |
| Training_Data keyword audit | 0 | 0 | 0.000% | 0 | 0.000% | 0 |

Coverage interpretation:

- R39 safe training uses only 20 rectangle pairs out of 1240 pairs.
- R40 training uses 50 rectangle pairs and 80 micro-grid pairs out of 1300 pairs.
- Training_Data keyword audit found 0 checker/checkboard/chessboard-specific paths.
- The validation sets are shape or microscopy validation sets, not real checkboard-corner validation sets.

## Root-Cause Assessment

High confidence: the weak checkboard result is not explained only by the shared abnormal displacement interval.

The stronger explanation is a target-domain mismatch:

- The current model is being asked to reconstruct a real checkboard corner family it was not explicitly trained or validated on.
- It learned to create sharper-looking edges, but not to preserve the exact square-corner geometry needed by this sample.
- The validation checkpoint choice can therefore look good on synthetic shape/microscopy validation while still damaging real checkboard corners.

Medium confidence: the Lab PSF may contribute to the artifact, because an imperfect blur model can teach the model the wrong edge compensation.

Lower confidence: a basic inference/package mistake, because the five cases have matching filenames and frame counts and the distortion repeats systematically.

## Recommended Next Evidence

1. Add a Lab checkboard/corner validation family before more full training.
2. Include sharp right angles, blurred right angles, varied brightness, varied cell widths, and off-center corners.
3. Score candidates with corner-response shift and visual contact sheets before external GMF.
4. Only after the corner check passes should R39/R40 averaging or longer training be treated as meaningful for this sample.

## Generated Files

- Corner metrics table: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation/corner_metrics_per_measurement.csv`
- Corner summary table: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation/corner_metrics_summary.csv`
- Training coverage table: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation/training_data_coverage_summary.csv`
- Visual corner sheet: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation/corner_patch_contact_sheet.png`
- Metric chart: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation/corner_metric_summary.png`
