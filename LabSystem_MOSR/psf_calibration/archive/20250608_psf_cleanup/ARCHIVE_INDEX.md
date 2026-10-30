# PSF Cleanup Archive Index

Date: 2026-06-08

This archive keeps superseded lab PSF calibration material for traceability.
The current formal BADS candidate is the validated fine pre-alignment
inner-circle ROI fit.

## Current Formal Path

- Formal ROI config: `../../configs/inner_circle_roi_fine_prealign_20250608.json`
- Formal ROI images: `../../inputs/20250605_inner_circle_roi/measured/`
- Formal ROI GT: `../../inputs/20250605_inner_circle_roi/GT/LAB_INNER_CIRCLE_GT_901.bmp`
- Formal PSF result: `../../results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`
- Formal validation report: `../../results/20250605_inner_circle_roi_fine_prealign_validation/VALIDATION_REPORT.md`

## Archived Material

| Archive item | Original role | Why archived |
|---|---|---|
| `configs/standard_wholefov_20250605.fullframe_blocked.json` | Full-frame standard PSF config | Superseded by inner-circle ROI because full-frame chart content contaminates the fit. |
| `inputs/20250605_standard_wholefov_fullframe_blocked/` | Full-frame staged measured images and placeholder GT path | Superseded blocked staging; kept for traceability only. |
| `scripts/run_lab_wholefov_standard_fit.m` | Full-frame MATLAB run entry | Superseded blocked entry; formal run now uses the ROI runner. |
| `scripts/preflight_lab_wholefov_standard_fit.m` | Full-frame MATLAB preflight | Superseded blocked entry; formal preflight now uses the ROI preflight. |
| `configs/psf_calibration_20250605.edge_exploratory.json` | Edge-derived Gaussian exploratory config | Not the formal PSF fitting method. |
| `results/20250605_edge_psf_exploratory/` | Edge-derived Gaussian exploratory output | Useful sanity check only; not a training PSF input. |
| `scripts/calibrate_edge_psf.py` | Edge-derived exploratory script | Not part of the formal copied Whole-FOV fitter path. |
| `tests/test_edge_psf_calibration.py` | Tests for exploratory edge script | Archived with the exploratory script. |
| `results/20250605_inner_circle_probe_intermediate/` | Intermediate inner-circle detection work area | Useful detection files were moved to the active ROI input folder. |
| `results/20250605_inner_circle_roi_smoke1/` | Temporary one-image smoke fit output | Superseded by the completed 25-image formal fit. |
| `configs/inner_circle_roi_standard_wholefov_20250605.superseded_by_fine.json` | First 25-image BADS config | Superseded by the fine pre-alignment run. |
| `scripts/run_lab_inner_circle_roi_standard_fit.m` | First 25-image BADS runner | Superseded by the fine pre-alignment runner. |
| `results/20250605_inner_circle_roi_standard_fit_superseded_by_fine/` | First 25-image BADS fit output | Slightly worse and less centroid-stable than the fine pre-alignment fit; kept as comparison evidence. |
| `results/20250605_inner_circle_roi_validation_superseded_by_fine/` | First 25-image BADS validation output | Kept to reproduce the standard-vs-fine comparison. |

## Active Detection Evidence

The active ROI input folder now owns the detection evidence used by the GT
preparation script:

- `../../inputs/20250605_inner_circle_roi/detection/inner_white_disk_component.csv`
- `../../inputs/20250605_inner_circle_roi/detection/inner_white_disk_component_contact.png`
