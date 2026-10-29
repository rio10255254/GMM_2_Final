# 20250605 Checkboard External GMF Package

This folder prepares the laboratory continuous-displacement checkboard capture
for external GMF validation.

## Source Sequence

- Input capture folder: `Thesis_MOSR_Evidence/20250605_checkboard`
- Image count: 51 BMP frames
- First frame: `Image__2026-06-05__16-04-32.bmp`
- Last frame: `Image__2026-06-05__16-14-03.bmp`
- Image size: 2048 x 1536
- Mode: grayscale

## GMF Cases

Use the folders under `gmf_cases/` as the external GMF input cases.

| Case | Meaning | Frame count |
|---|---|---:|
| `raw_input/` | Original laboratory checkboard sequence, copied without reconstruction. | 51 |
| `lab_r39_latest/` | Reconstruction from the Lab R39 formal 100-epoch output. | 51 |
| `lab_r40_latest/` | Reconstruction from the Lab R40 formal 100-epoch output. | 51 |
| `lab_r39_best_tradeoff/` | Reconstruction from the Lab R39 auto tradeoff checkpoint. | 51 |
| `lab_r40_best_tradeoff/` | Reconstruction from the Lab R40 auto tradeoff checkpoint. | 51 |
| `lab_r46_best_tradeoff/` | Reconstruction from the Lab R46 tradeoff checkpoint. | 51 |
| `lab_r46_best_detail_guarded/` | Reconstruction from the Lab R46 detail-guarded checkpoint. | 51 |
| `lab_r46_latest/` | Reconstruction from the Lab R46 final epoch checkpoint. | 51 |
| `lab_r47_best_tradeoff/` | Reconstruction from the Lab R47 epoch 33 trainer-selected checkpoint. | 51 |
| `lab_r47_latest/` | Reconstruction from the Lab R47 epoch 200 final checkpoint. | 51 |

All cases preserve exactly the same BMP filenames. Sort by filename before
running external GMF.

## Reconstruction Inputs

| Item | Value |
|---|---|
| Inference script | `LabSystem_MOSR/scripts/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py` |
| R39 weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260609_173931/weights/latest.pth.tar` |
| R40 weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260609_185153/weights/latest.pth.tar` |
| R39 tradeoff weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260609_173931/weights/best_tradeoff.pth.tar` |
| R40 tradeoff weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260609_185153/weights/best_tradeoff.pth.tar` |
| R46 tradeoff weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_112100/weights/best_tradeoff.pth.tar` |
| R46 detail weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_112100/weights/best_detail_guarded.pth.tar` |
| R46 latest weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_112100/weights/latest.pth.tar` |
| R47 tradeoff weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r47_realistic_boundary_r39_latest_20260612_171140/weights/best_tradeoff.pth.tar` |
| R47 latest weights | `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r47_realistic_boundary_r39_latest_20260612_171140/weights/latest.pth.tar` |
| PSF | `LabSystem_MOSR/psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat` |
| Selection mode | `all` |

## Generated Output Folders

| Case | Direct reconstruction output |
|---|---|
| R39 | `reconstruct_progress_latest_in_20250605_checkboard_20260609_173931/lab_r39_latest/` |
| R40 | `reconstruct_progress_latest_in_20250605_checkboard_20260609_185153/lab_r40_latest/` |
| R39 tradeoff | `reconstruct_progress_best_tradeoff_in_raw_input_20260609_173931/lab_r39_best_tradeoff/` |
| R40 tradeoff | `reconstruct_progress_best_tradeoff_in_raw_input_20260609_185153/lab_r40_best_tradeoff/` |
| R46 tradeoff | `reconstruct_progress_best_tradeoff_in_20250605_checkboard_20260612_112100/lab_r46_best_tradeoff/` |
| R46 detail | `reconstruct_progress_best_detail_guarded_in_20250605_checkboard_20260612_112100/lab_r46_best_detail_guarded/` |
| R46 latest | `reconstruct_progress_latest_in_20250605_checkboard_20260612_112100/lab_r46_latest/` |
| R47 tradeoff | `reconstruct_progress_best_tradeoff_in_20250605_checkboard_20260612_171140/lab_r47_best_tradeoff/` |
| R47 latest | `reconstruct_progress_latest_in_20250605_checkboard_20260612_171140/lab_r47_latest/` |

Run logs are stored in `run_logs/`.

## Corner Geometry Validation

The checkboard corner validation was added after visual inspection showed that
some reconstructed right angles were being reshaped.

| Item | Location |
|---|---|
| Re-runnable validator | `validate_checkboard_corner_geometry.py` |
| Validation outputs | `corner_geometry_validation/` |
| Canonical report | `LabSystem_MOSR/Experiments/reports/LAB_CHECKBOARD_CORNER_VALIDATION_20260611.md` |
| R46 validation outputs | `corner_geometry_validation_r46_20260612/` |
| R46 canonical report | `LabSystem_MOSR/Experiments/reports/LAB_R46_CHECKBOARD_CORNER_VALIDATION_20260612.md` |
| R47 validation runner | `validate_checkboard_corner_geometry_r47.py` |
| R47 validation outputs | `corner_geometry_validation_r47_20260613/` |
| R47 canonical report | `LabSystem_MOSR/Experiments/R47_RealisticBoundaryGeneralization/reports/R47_CHECKBOARD_VALIDATION_20260613.md` |

The original 2026-06-11 validation checked all 51 frames and 358 raw
checkboard corners. It found that reconstructed cases frequently move the
strongest local corner response away from the raw corner location. The 2026-06-12
R46 update added synthetic checkboard/corner training data, but the real captured
checkboard corner validation still did not pass. The 2026-06-13 R47 update
tested the 4000-pair realistic-boundary model, but it also did not pass the real
corner validation.

## Verification

Completed on 2026-06-09.

| Check | Result |
|---|---|
| Case counts | `raw_input=51`, `lab_r39_latest=51`, `lab_r40_latest=51`, `lab_r39_best_tradeoff=51`, `lab_r40_best_tradeoff=51` |
| Filename identity | Passed; all 2026-06-09 baseline cases have identical filenames. |
| Dimensions | Passed; all frames are 2048 x 1536. |
| Image mode | Passed; all frames are grayscale. |
| R39 mean absolute difference vs raw | 1.797 gray levels on average. |
| R40 mean absolute difference vs raw | 2.023 gray levels on average. |
| R39 tradeoff mean absolute difference vs raw | 1.408 gray levels on average. |
| R40 tradeoff mean absolute difference vs raw | 1.389 gray levels on average. |

The MATLAB PSF file reader emitted a duplicate-variable warning for the `None`
variable inside the `.mat` file. The inference still loaded the PSF and
completed all frames successfully.

## R46 Update

Completed on 2026-06-12.

| Check | Result |
|---|---|
| R46 case counts | `lab_r46_best_tradeoff=51`, `lab_r46_best_detail_guarded=51`, `lab_r46_latest=51` |
| Filename identity | Passed; all R46 cases match raw input filenames. |
| Dimensions | Passed; all R46 frames are 2048 x 1536. |
| Image mode | Passed; all R46 frames are grayscale. |
| R46 tradeoff mean absolute difference vs raw | 1.657 gray levels on average. |
| R46 detail mean absolute difference vs raw | 1.848 gray levels on average. |
| R46 latest mean absolute difference vs raw | 2.198 gray levels on average. |
| Corner validation | R46 did not solve the rounded-corner problem; R46 tradeoff is the least-bad R46 candidate. |

## R47 Update

Completed on 2026-06-13.

| Check | Result |
|---|---|
| R47 case counts | `lab_r47_best_tradeoff=51`, `lab_r47_latest=51` |
| Filename identity | Passed; both R47 cases match raw input filenames. |
| Dimensions | Passed; all R47 frames are 2048 x 1536. |
| Image mode | Passed; all R47 frames are grayscale. |
| R47 tradeoff mean absolute difference vs raw | 1.506 gray levels on average. |
| R47 latest mean absolute difference vs raw | 1.625 gray levels on average. |
| Corner validation | R47 did not solve the rounded-corner problem; epoch 200 is less bad than epoch 33, but neither should be promoted. |
| External GMF scores | Pending; no `GMF_score.txt` files were present for the R47 cases at report generation time. |

## External GMF Note

No frame was removed or renamed in this package. If the external GMF tool cannot
score the first interval or treats the first step as a warm-up, record that in
the returned score report instead of modifying this package.
