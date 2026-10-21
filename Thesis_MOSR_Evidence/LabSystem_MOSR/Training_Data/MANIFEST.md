# Training_Data Manifest

Last updated: 2026-06-12

## Naming Check

| Item | Status | Note |
|---|---|---|
| `Training_Data/` | standard | Matches the main project data root name. |
| `Data_Simulaion.py` | copied standard | Filename intentionally keeps the original typo. |
| `PSF_Convolution.py` | copied standard with lab controls | Algorithm is reused; default PSF path points to the lab validated PSF; Gaussian control can be selected by environment variable. |
| `generated/` | stage 1-33 generated | Clean GT output root; main geometry/ring plus R40 microscopy clean data. |
| `generated_convolved/` | stage 1-33 generated | Formal Lab BADS-PSF convolved input root. |
| `generated_convolved_gaussian_control/` | stage 1-33 generated | Gaussian-control convolved input root with sigma 3.5 px; comparison only. |
| `tra_src_ring/` | stage 1 ring replay built | Lab replacement for main training sources; built from Lab-generated data only. |
| `tra_lbl_ring/` | stage 1 ring replay built | Lab replacement for main training labels; paired with `tra_src_ring/`. |
| `r46_corner_aware_finetune/` | R46 checkboard/corner packages built | Adds Lab checkboard/right-angle corner coverage for the 20250605 checkboard reconstruction issue. |
| `scripts/build_lab_ring_package.py` | lab helper | Builds ring replay from Lab generated/convolved data only. |
| `lab_data_generation/` | legacy planning folder | Not the formal data root; kept as old planning context only. |

## Copied Sources

| Lab file | Copied from |
|---|---|
| `Training_Data/Data_Simulaion.py` | `D:/GMM_2_Final/Training_Data/Data_Simulaion.py` |
| `Training_Data/PSF_Convolution.py` | `D:/GMM_2_Final/Training_Data/PSF_Convolution.py` |
| `Experiments/R39_ShapeGeneralization/scripts/r39_shape_data.py` | `D:/GMM_2_Final/Experiments/R39_ShapeGeneralization/scripts/r39_shape_data.py` |
| `Experiments/R40_MicroscopyFeatureCoverage/scripts/r40_micro_data.py` | `D:/GMM_2_Final/Experiments/R40_MicroscopyFeatureCoverage/scripts/r40_micro_data.py` |

## Lab Extensions

| Lab file | Role |
|---|---|
| `Experiments/R46_CornerAwareFineTune/scripts/r46_corner_data.py` | Lab checkboard/corner data builder, based on the R40 package-builder pattern and the main-project R46 lesson. |
| `Experiments/R46_CornerAwareFineTune/scripts/launch_r46.py` | Conservative Lab R46 fine-tune launcher using the new corner package. |

## Lab-Specific Difference

`Data_Simulaion.py` and `PSF_Convolution.py` keep the original project filenames
and roles. Lab-specific controls are limited to environment variables for
selected stages, seeds, output roots, and PSF mode.

`PSF_Convolution.py` uses the lab PSF by default:

`LabSystem_MOSR/psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`

Everything else should remain as close as possible to the original project
until there is a real lab-system reason to diverge.

## First Generated Round

Date: 2026-06-08

Scope:
- Stage 25: macro clean annulus GMF sequence, 75 clean GT images.
- Stage 26: macro defect annulus GMF sequence, 75 clean GT images.
- Formal BADS PSF convolved inputs: 150 images.
- Gaussian control convolved inputs: 150 images, sigma 3.5 px.

Validation:
- Counts match across clean GT, BADS PSF, and Gaussian control.
- Sample images are 512x512 uint16.
- BADS and Gaussian outputs differ from each other on the checked sample.
- Preview: `Training_Data/reports/stage25_26_first_generation_preview.png`

## Stage 1-33 Data Foundation

Date: 2026-06-08

Scope:
- Stage 1-28 main geometry, annulus, defect, and displacement sequence data.
- Stage 29-33 R40 microscopy features.
- Formal Lab BADS PSF inputs for all stage 1-33 images.
- Gaussian-control inputs for all stage 1-33 images.
- Lab ring replay package with 1100 pairs.
- Lab R39 and R40 packages materialized from Lab data only.

Counts:
- Clean GT: 2968 images.
- Lab BADS PSF convolved inputs: 2968 images.
- Gaussian-control convolved inputs: 2968 images.
- Ring replay: 1100 pairs.
- R39 packages: 1240 / 1590 / 210 pairs.
- R40 packages: 1300 / 100 pairs.

Report:

`Training_Data/reports/LAB_TRAINING_DATA_STAGE01_33_20250608.md`

Preview:

`Training_Data/reports/lab_training_data_stage01_33_preview.png`

## R46 Checkboard/Corner Extension

Date: 2026-06-12

Scope:
- Stage 48 Lab checkboard/right-angle corner clean GT, 500 images.
- Formal Lab BADS PSF convolved inputs, 500 images.
- Gaussian-control convolved inputs, 500 images.
- R46 checkboard/corner training package, 1550 pairs.
- Held-out checkboard/corner validation package, 100 pairs.
- R46 Lab launcher dry-run and 1-epoch/1-batch smoke training verified.

Report:

`Training_Data/reports/LAB_R46_CHECKBOARD_CORNER_DATA_20260612.md`

Preview:

`Training_Data/reports/r46_checkboard_corner_preview.png`
