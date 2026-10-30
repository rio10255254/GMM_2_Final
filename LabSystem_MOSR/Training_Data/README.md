# Lab Training_Data

This is the lab-system copy of the original project's `Training_Data` workflow.

The rule for this area is simple: keep the same filenames and the same roles as
the main project wherever possible. Lab-specific changes should be limited to
paths, manifests, and the selected lab PSF.

## Standard Files

| Item | Role |
|---|---|
| `Data_Simulaion.py` | Same clean-GT generator copied from the main project. |
| `PSF_Convolution.py` | Same PSF-convolution workflow copied from the main project, with the default PSF path changed to the validated lab PSF. |
| `generated/` | Clean GT images. Current completed scope: stage 1-33 plus Lab stage 48 checkboard corners. |
| `generated_convolved/` | Formal BADS-PSF convolved lab inputs. Current completed scope: stage 1-33 plus Lab stage 48. |
| `generated_convolved_gaussian_control/` | Gaussian-control comparison inputs. Current completed scope: stage 1-33 plus Lab stage 48 with sigma `3.5 px`. |
| `tra_src_ring/` | Lab ring replay source package, built from Lab-generated data only. |
| `tra_lbl_ring/` | Lab ring replay label package, paired with `tra_src_ring/`. |
| `r39_shape_generalization/` | Lab R39-style shape package output. |
| `r40_microscopy_feature_coverage/` | Lab R40-style microscopy package output. |
| `r46_corner_aware_finetune/` | Lab R46 checkboard/corner package output. |
| `scripts/build_lab_ring_package.py` | Lab helper for rebuilding `tra_src_ring/` and `tra_lbl_ring/`. |

## Current PSF Input

The formal BADS PSF is:

`../psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`

The first lab data-generation round should still keep a Gaussian control
comparison with sigma `3.5 px`, because PSF validation showed the global
Gaussian remains a useful control even though the fine pre-aligned BADS fit is
the current formal candidate.

## First Completed Data Round

The first generated round is intentionally narrow and uses the macro GMF
sequence stages first:

| Set | Stage 25 | Stage 26 | Total |
|---|---:|---:|---:|
| Clean GT | 75 | 75 | 150 |
| BADS-PSF convolved inputs | 75 | 75 | 150 |
| Gaussian-control convolved inputs | 75 | 75 | 150 |

The visual preview for this round is:

`reports/stage25_26_first_generation_preview.png`

## Current Completed Data Foundation

The current completed LabSystem data foundation now covers the main-project
success path up through R39/R40:

| Set | Scope | Total |
|---|---|---:|
| Clean GT | stage 1-33 | 2968 images |
| BADS-PSF convolved inputs | stage 1-33 | 2968 images |
| Gaussian-control convolved inputs | stage 1-33 | 2968 images |
| Ring replay | Lab ring stages | 1100 pairs |
| R39 shape packages | safe / strong / validation | 1240 / 1590 / 210 pairs |
| R40 microscopy packages | train / validation | 1300 / 100 pairs |

The detailed report is:

`reports/LAB_TRAINING_DATA_STAGE01_33_20250608.md`

The visual preview is:

`reports/lab_training_data_stage01_33_preview.png`

## R46 Checkboard/Corner Extension

The Lab checkboard reconstruction issue now has a dedicated corner data
extension:

| Set | Scope | Total |
|---|---|---:|
| Clean GT | stage 48 checkboard/corners | 500 images |
| BADS-PSF convolved inputs | stage 48 | 500 images |
| Gaussian-control convolved inputs | stage 48 | 500 images |
| R46 train package | ring + shape + micro + corner | 1550 pairs |
| R46 held-out validation | corner only | 100 pairs |

The detailed report is:

`reports/LAB_R46_CHECKBOARD_CORNER_DATA_20260612.md`

The visual preview is:

`reports/r46_checkboard_corner_preview.png`

## First Recommended Build Order

1. Use the completed stage 1-33 data foundation for the first LabSystem
   training launch.
2. Start with the COMBO-like lab baseline, then reproduce R39/R40 style
   training on Lab data.
3. Keep Gaussian-control data for PSF comparison only, not as the formal
   training source.
