# LabSystem_MOSR

研究閱讀先看[Lab全線與原資料](../docs/reproducibility/lineage/LAB_SYSTEM.md)、[V42原歷程](../docs/reproducibility/lab_comparisons/V42_HISTORY.md)；主R輪次及目前R152／RAW論文另看[全研究沿革](../docs/reproducibility/lineage/README.md)。下方原啟動／bootstrap說明保留原日期，不作今日完整狀態。

2026-10-22研究歷史補註：[Lab校正、資料基礎、R39／R40、R46至62、V41／V42及平行比較](../docs/reproducibility/lineage/LAB_SYSTEM.md)已有串聯入口。下方Current Scope保留建立時的狀態，不表示後來Lab停在R48。資料stage01至33是生成類型，不是33次獨立訓練；現在論文採用仍以PROJECT_STATE.md及R153交接為準。

2026-09-24 新控制程式的效果錄影（三支 MP4）在 [control_program_recordings_20260924](control_program_recordings_20260924/README.md)，影片本身在發布附件。

This area is the isolated MOSR line for the laboratory imaging system.

It is intentionally separated from the original industry-project experiment
history under `Experiments`. The original project remains the
method and baseline reference. This area records the lab-system replication:
lab PSF calibration first, then lab data generation, lab training, lab
inference, and lab validation.

## Current Scope

The active work is PSF calibration from the laboratory calibration target
images stored in the `20250605_PSF_Calibration` batch. The image filenames show
the capture date as 2026-06-05.

The formal path reuses the original project Whole-FOV Zernike/BADS PSF fitting
workflow. The lab-specific inner-circle ROI run has completed using the
`phi 0.1 mm` target under the Basler acA2040-120um + 20x setup. The PSF
validation package accepted the fit as usable for the next phase. A finer
pre-alignment refit was then run and selected as the BADS candidate because it
is slightly better and much more centroid-stable, while still keeping a `3.5 px`
Gaussian control for the first lab data-generation comparison.

The first narrow lab data-generation round completed for the macro GMF sequence
stages 25 and 26. The broader LabSystem data foundation now covers stages 1-33:
main geometry/ring data, R40 microscopy features, formal BADS-PSF inputs,
Gaussian-control inputs, Lab ring replay, and R39/R40 training packages.

The first Lab training bootstrap and the first formal 100-epoch Lab training
pass have completed. R39 safe and R40 combo now have Lab-specific launchers,
dry-run checks, 1-epoch smoke runs, 25-epoch bootstrap runs, and 100-epoch
formal runs. The launchers automatically rebuild Lab PSF buffers while
inheriting the old project model weights. The first Lab inference package has
also been prepared for the 20250605 checkboard continuous-displacement sequence
and scored with external GMF. Follow-up corner validation showed the current
models still round checkboard corners, so Lab R46 and R47 boundary-focused
extensions were built. R47 completed a full 200-epoch training run and both
R47 checkpoints were reconstructed on the real 20250605 checkboard sequence.
The real corner validation did not pass: epoch 200 is less bad than epoch 33,
but neither checkpoint fixes the rounded-corner issue. R48 then tested a
real-corner transfer line with Lab checkboard-like corner data and geometry
sidecars. R48 also completed 200-epoch training and real checkboard
reconstruction, but it failed the same corner validation and produced stronger
corner artifacts than the earlier Lab controls.

## Layout

| Path | Purpose |
|---|---|
| `Training_Data/` | Lab-system copy of the main project's training-data workflow. |
| `Experiments/R39_ShapeGeneralization/` | Lab copy of the R39 shape data-package builder area. |
| `Experiments/R40_MicroscopyFeatureCoverage/` | Lab copy of the R40 microscopy data-package builder area. |
| `Experiments/R46_CornerAwareFineTune/` | Lab checkboard/corner data extension and conservative fine-tune launcher. |
| `Experiments/R47_RealisticBoundaryGeneralization/` | Lab realistic boundary/generalization data expansion and 200-epoch training run. |
| `Experiments/R48_RealCornerTransfer/` | Lab real-corner transfer data package, geometry sidecars, completed 200-epoch run, and failed real-corner validation. |
| `Experiments/reports/` | Lab training and validation handoff reports. |
| `scripts/` | Lab-system copies of reusable project scripts used after training. |
| `Reconstruct_Progress/` | Lab-system reconstruction outputs and external validation packages. |
| `psf_calibration/` | Lab-system PSF calibration workflow and outputs. |
| `psf_calibration/raw/` | Archived raw calibration captures used by this line. |
| `psf_calibration/scripts/` | Re-runnable calibration scripts. |
| `psf_calibration/results/` | Generated numeric outputs and figures. |
| `psf_calibration/reports/` | Human-readable summaries for handoff and thesis use. |
| `psf_calibration/archive/` | Superseded exploratory or blocked PSF material kept for traceability. |
| `lab_data_generation/` | Legacy planning note only; formal data root is `Training_Data/`. |

## PSF Calibration Status

| Path | Status |
|---|---|
| `psf_calibration/scripts/standard_wholefov/` | Project-standard fitter copied from `PSF_Fitting`. |
| `psf_calibration/scripts/run_lab_inner_circle_roi_fine_prealign_fit.m` | Current lab ROI PSF fit entry point. |
| `psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/` | Current validated BADS candidate for lab data generation. |
| `psf_calibration/results/20250605_inner_circle_roi_fine_prealign_validation/` | Current forward-model PSF validation. |
| `psf_calibration/reports/FINE_PREALIGN_COMPARISON_20250608.md` | Standard-vs-fine PSF comparison. |
| `Training_Data/Data_Simulaion.py` | Main-project clean-GT generator copied for lab use. |
| `Training_Data/PSF_Convolution.py` | Main-project PSF convolution copied for lab use; default PSF points to the validated lab fit. |
| `Training_Data/configs/lab_data_generation_20250605.json` | Lab training-data config; stage 1-33 + R39/R40 completed. |
| `Training_Data/reports/FIRST_SEQUENCE_GENERATION_20250608.md` | First lab sequence generation report. |
| `Training_Data/reports/LAB_TRAINING_DATA_STAGE01_33_20250608.md` | Current Lab data foundation report. |
| `Training_Data/reports/lab_training_data_stage01_33_preview.png` | Current Lab data foundation preview. |
| `Experiments/R39_ShapeGeneralization/scripts/r39_shape_data.py` | Main-project R39 data-package builder copied for future lab shape packages. |
| `Experiments/R40_MicroscopyFeatureCoverage/scripts/r40_micro_data.py` | Main-project R40 data-package builder copied for future lab microscopy packages. |
| `Experiments/R39_ShapeGeneralization/scripts/launch_r39.py` | Lab R39 training launcher; reuses main model code and mounts Lab PSF/data/output. |
| `Experiments/R40_MicroscopyFeatureCoverage/scripts/launch_r40.py` | Lab R40 training launcher; reuses main model code and mounts Lab PSF/data/output. |
| `Experiments/R46_CornerAwareFineTune/scripts/r46_corner_data.py` | Lab R46 checkboard/corner data builder. |
| `Experiments/R46_CornerAwareFineTune/scripts/launch_r46.py` | Lab R46 conservative corner fine-tune launcher. |
| `Experiments/R47_RealisticBoundaryGeneralization/scripts/r47_realistic_boundary_data.py` | Lab R47 realistic boundary data builder. |
| `Experiments/R47_RealisticBoundaryGeneralization/scripts/launch_r47.py` | Lab R47 formal 200-epoch training launcher. |
| `Experiments/R48_RealCornerTransfer/scripts/r48_real_corner_data.py` | Lab R48 real-corner data builder with geometry sidecars. |
| `Experiments/R48_RealCornerTransfer/scripts/launch_r48.py` | Lab R48 formal training launcher with Lab PSF and geometry sidecars. |
| `Experiments/R48_RealCornerTransfer/reports/R48_RESULTS_20260614.md` | Lab R48 200-epoch training and real-corner validation summary; R48 did not pass. |
| `Experiments/R48_RealCornerTransfer/reports/R48_CHECKBOARD_VALIDATION_20260613.md` | Lab R48 real checkboard validation report; R48 worsened the corner metric. |
| `Experiments/reports/LAB_TRAINING_BOOTSTRAP_20250608.md` | Current Lab training bootstrap report. |
| `Experiments/reports/LAB_FORMAL_TRAINING_100E_20260609.md` | Current Lab formal 100-epoch training report. |
| `Experiments/reports/LAB_CHECKBOARD_EXTERNAL_GMF_20260611.md` | Current Lab checkboard external GMF result report. |
| `Training_Data/reports/LAB_R46_CHECKBOARD_CORNER_DATA_20260612.md` | Lab R46 checkboard/corner data and smoke-training report. |
| `Training_Data/reports/LAB_R47_REALISTIC_BOUNDARY_DATA_20260612.md` | Lab R47 realistic boundary data report. |
| `Training_Data/reports/LAB_R48_REAL_CORNER_DATA_20260613.md` | Lab R48 real-corner data and smoke-training report. |
| `Experiments/R47_RealisticBoundaryGeneralization/reports/R47_RESULTS_20260613.md` | Lab R47 200-epoch training report. |
| `Experiments/R47_RealisticBoundaryGeneralization/reports/R47_CHECKBOARD_VALIDATION_20260613.md` | Lab R47 real checkboard validation report; R47 did not pass. |
| `scripts/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py` | Main-project inference script copied for LabSystem use; defaults point to Lab input, Lab PSF, and Lab reconstruction output. |
| `Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/` | Current Lab checkboard reconstruction package and external GMF analysis outputs. |
| `psf_calibration/archive/20250608_psf_cleanup/` | Archived full-frame blocked staging, edge exploratory pass, smoke/intermediate results, and the superseded first BADS fit. |

## Current Training-Data Boundary

The first formal LabSystem training-data foundation includes stages 1-33 and
the R39/R40 package path. The Lab checkboard problem now has targeted R46, R47,
and R48 extensions, kept separate from the original foundation. R47 adds a
4000-pair realistic boundary/generalization training package plus an 800-pair
held-out validation package, but its real checkboard validation failed. R48 adds
a 6000-pair real-corner training package, a 1200-pair held-out real-corner
package, and geometry sidecars for every packaged image, but it also failed the
real checkboard validation. R47 and R48 are evidence for the next redesign
rather than promotable Lab models.

## Boundary

Do not promote files here into the original project baseline state. Lab-system
results should be compared against the old project only as method transfer
evidence, not as a replacement for the industry-system baselines.
