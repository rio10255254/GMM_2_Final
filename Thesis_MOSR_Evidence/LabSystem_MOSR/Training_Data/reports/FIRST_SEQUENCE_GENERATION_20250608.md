# First Lab Sequence Generation - 2026-06-08

## Purpose

Generate the first usable lab-system training-data round after PSF calibration,
while keeping the main-project data-generation workflow and filenames.

This first round is limited to the macro GMF sequence stages:

| Stage | Role | Count |
|---|---|---:|
| 25 | Clean macro annulus 8 px sequence | 75 |
| 26 | Defect macro annulus 8 px sequence | 75 |

Full all-stage generation is not complete yet.

## Inputs

Clean GT generator:

`Training_Data/Data_Simulaion.py`

Formal BADS PSF:

`LabSystem_MOSR/psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`

Gaussian control:

`sigma = 3.5 px`

Fixed noise seed:

`42`

## Outputs

| Output set | Root | Stage 25 | Stage 26 | Total |
|---|---|---:|---:|---:|
| Clean GT | `Training_Data/generated/` | 75 | 75 | 150 |
| BADS PSF convolved | `Training_Data/generated_convolved/` | 75 | 75 | 150 |
| Gaussian control convolved | `Training_Data/generated_convolved_gaussian_control/` | 75 | 75 | 150 |

Preview:

`Training_Data/reports/stage25_26_first_generation_preview.png`

## Validation

Fresh checks completed on 2026-06-08:

- `Data_Simulaion.py` and `PSF_Convolution.py` parse successfully.
- Environment stage selection chooses only stages 25 and 26.
- Each generated output set has 150 images.
- Sample image shape is `512x512`, dtype is `uint16`.
- The BADS PSF and Gaussian control outputs differ on the checked sample.
- No long-running Python generation process remained after completion.

Checked sample:

`stage_25_annulus_gmf_sequence_macro_clean/2151_seq000_f00.tif`

Sample summary:

| Set | Mean | Std | Note |
|---|---:|---:|---|
| Clean GT | 33700.65 | 2035.62 | Sharp GT edge |
| BADS PSF | 33700.73 | 1301.47 | Lab PSF blur + noise |
| Gaussian control | 33700.20 | 1500.28 | Gaussian blur + same noise seed |

Mean absolute difference between BADS PSF and Gaussian control on the checked
sample: `508.75` gray levels.

## Notes

An initial full all-stage generation attempt was stopped because it was too slow
for the immediate first-round need and had only produced partial intermediate
outputs. Those partial outputs were removed before this formal stage 25/26 run.

The next step is to define the first train/validation split and package these
lab-generated outputs into the standard `tra_src_ring/` and `tra_lbl_ring/`
layout.
