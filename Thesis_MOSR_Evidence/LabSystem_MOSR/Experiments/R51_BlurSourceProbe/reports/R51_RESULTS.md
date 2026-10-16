# R51 Blur-Source Probe Results

Date: 2026-06-14

## Verdict

R51 is a useful direction, but it is not a promoted Lab model.

The mixed-PSF short probe produced the best real checkboard result. It reduced
the median corner shift from the Lab R40 control's `4.243 px` to `2.828 px`.
However, it still increased the large-shift corner rate from `24.581%` to
`36.872%`. This means the typical corner response improved, but the output is
not stable enough.

## What Was Tested

R51 compared three blur-source choices for checkboard-corner training:

| Candidate | Corner blur source | Training pairs |
|---|---|---:|
| R51 Gaussian | Gaussian corner blur | 1550 |
| R51 weak-BADS | BADS PSF weakened to alpha 0.50 | 1550 |
| R51 mixed-PSF | formal BADS, Gaussian, and weak-BADS mixed | 1550 |

All three packages reused the Lab ring, shape, and microscopy coverage instead
of becoming corner-only training data.

## Training

All three candidates started from the Lab R40 `best_tradeoff` checkpoint and
used the Lab PSF path with checkpoint PSF loading disabled. This keeps the
comparison focused on the training data blur source.

| Candidate | Run | Result |
|---|---|---|
| R51 Gaussian | `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_gaussian_corner_probe_short_e012_b080_20260614_215954` | completed |
| R51 weak-BADS | `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_weak_bads_corner_probe_short_e012_b080_20260614_220314` | completed |
| R51 mixed-PSF | `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_mixed_psf_corner_probe_short_e012_b080_20260614_220602` | completed |

Each short probe ran for 12 epochs with 80 train batches per epoch. A smoke
run was completed before the three probe runs.

## Real Checkboard Validation

Validation used the real Lab `20250605_checkboard` sequence:

- Frames checked: 51
- Raw checker corners accepted: 358
- R51 reconstruction cases: 6
- Every R51 case preserved the original 51 BMP filenames

| Case | Median corner shift | Corners > 5 px |
|---|---:|---:|
| Lab R40 tradeoff | 4.243 px | 24.581% |
| R51 Gaussian best | 3.606 px | 37.989% |
| R51 weak-BADS best | 3.606 px | 37.151% |
| R51 mixed-PSF best | 2.828 px | 36.872% |

R51 mixed-PSF is the best R51 candidate, but it does not beat R40 on the
large-shift stability metric.

## Interpretation

R50 was right that formal BADS alone is too soft as the only Lab
checkboard-corner blur truth. R51 shows that changing the blur source can help
the typical corner location, especially when several blur sources are mixed.

But the large-shift rate remains too high. This points to a selection/training
constraint problem, not only a PSF problem. The next Lab round should keep the
mixed-PSF direction and add a real-corner stability guard before a long formal
training run.

## Canonical Evidence

| Evidence | Location |
|---|---|
| Checkboard validation report | `reports/R51_CHECKBOARD_VALIDATION.md` |
| Experiment manifest | `MANIFEST.md` |
| Corner summary table | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/corner_metrics_summary.csv` |
| Corner validation summary | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/corner_validation_summary.json` |
| R51 reconstruction outputs | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/r51_reconstruction_outputs/` |
| R51 GMF-ready cases | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r51_*/` |
