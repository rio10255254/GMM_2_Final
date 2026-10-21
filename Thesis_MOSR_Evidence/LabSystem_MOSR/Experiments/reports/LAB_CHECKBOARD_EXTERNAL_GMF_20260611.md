# Lab Checkboard External GMF Result

Date: 2026-06-11

## Scope

This report records the first external GMF readout for the LabSystem_MOSR
continuous-displacement checkboard sequence.

Compared cases:

- Raw laboratory capture
- Lab R39 formal 100-epoch reconstruction
- Lab R40 formal 100-epoch reconstruction
- Lab R39 auto tradeoff reconstruction
- Lab R40 auto tradeoff reconstruction

The GMF source files are stored under
`LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_results/`.

## Calibration

- Camera: Basler acA2040-120um
- Camera pixel size: 3.45 um
- Objective: 20x
- Object-plane pixel size: 0.1725 um/px
- Expected 1 um displacement: 5.797101 px

## Result

Lower `step_std` means the measured step-to-step displacement is steadier.

| Case | GMF rows | Mean step (px) | Mean step (um) | step_std (px) | step_std (um) | Change vs raw |
|---|---:|---:|---:|---:|---:|---:|
| Raw input | 50 | 5.831306 | 1.005900 | 0.260669 | 0.044965 | baseline |
| Lab R39 latest | 50 | 5.830673 | 1.005791 | 0.257648 | 0.044444 | -1.16% |
| Lab R40 latest | 50 | 5.830061 | 1.005686 | 0.255399 | 0.044056 | -2.02% |
| Lab R39 tradeoff | 50 | 5.830163 | 1.005703 | 0.254427 | 0.043889 | -2.39% |
| Lab R40 tradeoff | 50 | 5.830041 | 1.005682 | 0.255418 | 0.044059 | -2.01% |

The first captured image exists in the image package but is absent from all
five GMF text outputs:

- `Image__2026-06-05__16-04-32.bmp`

This leaves 50 GMF rows and 49 measured step intervals per case.

## Flagged Interval

One interval is z > 5 in all five cases:

| Case | Interval | Step (px) | Step (um) |
|---|---|---:|---:|
| Raw input | `16-07-42` -> `16-08-18` | 7.474 | 1.289 |
| Lab R39 latest | `16-07-42` -> `16-08-18` | 7.437 | 1.283 |
| Lab R40 latest | `16-07-42` -> `16-08-18` | 7.431 | 1.282 |
| Lab R39 tradeoff | `16-07-42` -> `16-08-18` | 7.396 | 1.276 |
| Lab R40 tradeoff | `16-07-42` -> `16-08-18` | 7.417 | 1.279 |

This interval is kept in the headline result because it appears in every case
and GMF scores remain high. It is more consistent with a shared capture/sequence
irregularity than a reconstruction-specific GMF failure.

If that single interval is removed only as a diagnostic, the full-series
`step_std` becomes:

| Case | step_std after removing flagged interval (px) |
|---|---:|
| Raw input | 0.109431 |
| Lab R39 latest | 0.113533 |
| Lab R40 latest | 0.109906 |
| Lab R39 tradeoff | 0.107612 |
| Lab R40 tradeoff | 0.108066 |

## Interpretation

By the raw external GMF result, all Lab reconstructions slightly reduce the
step-to-step variation. Lab R39 tradeoff is the best of the five, followed by
Lab R40 latest and Lab R40 tradeoff, which are nearly tied.

The improvement is still small. Treat this as first LabSystem evidence for the
20250605 checkboard capture, not as a final model-selection verdict. If the
shared flagged interval is excluded, both tradeoff checkpoints beat raw; Lab R39
tradeoff is best in that diagnostic view.

## Generated Artifacts

- `analysis_summary.json`
- `analysis_summary.csv`
- `step_diagnostics.csv`
- `gmf_step_std_comparison.png`
- `GMF_ANALYSIS_20260611.md`
