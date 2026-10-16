# Lab-System PSF Calibration

This folder contains the laboratory-system PSF calibration workflow.

The formal path reuses the original project Whole-FOV Zernike/BADS fitting
workflow from `D:/GMM_2_Final/PSF_Fitting`. The copied MATLAB files are stored
under `scripts/standard_wholefov/` with a source manifest.

The `20250605_PSF_Calibration` image batch has been staged as 25 inner-circle
ROI measurement images. The formal lab PSF now uses this ROI run. Superseded
full-frame staging and the old edge-derived Gaussian pass are kept only in the
cleanup archive.

The prepared lab run uses the innermost white disk in the concentric-circle
pattern. With the Basler acA2040-120um, 20x objective, no relay magnification,
no binning, and no software scaling, the effective scale is `0.1725 um/px`.
The usable `phi 0.1 mm` disk is therefore `579.71 px` in the sharp GT. A 901x901
ROI batch has been prepared so the copied project fitter can run on the same
inner circle plus two-block target style used by the original project.

## Current Run

| Field | Value |
|---|---|
| Formal run ID | `20250605_inner_circle_roi_fine_prealign_fit` |
| Measurement image count | 25 |
| Inner-circle ROI status | validated |
| ROI config | `configs/inner_circle_roi_fine_prealign_20250608.json` |
| ROI GT | `inputs/20250605_inner_circle_roi/GT/LAB_INNER_CIRCLE_GT_901.bmp` |
| ROI detection evidence | `inputs/20250605_inner_circle_roi/detection/` |
| Formal ROI PSF output | `results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat` |
| Formal ROI fit summary | `results/20250605_inner_circle_roi_fine_prealign_fit/fit_summary.json` |
| Formal ROI validation | `results/20250605_inner_circle_roi_fine_prealign_validation/VALIDATION_REPORT.md` |
| Superseded first BADS fit | `archive/20250608_psf_cleanup/results/20250605_inner_circle_roi_standard_fit_superseded_by_fine/` |
| Fine comparison report | `reports/FINE_PREALIGN_COMPARISON_20250608.md` |
| Validation verdict | validated; keep Gaussian control for first data-generation comparison |
| ROI overlay check | `results/20250605_inner_circle_roi/inner_circle_roi_gt_overlay_contact.png` |
| Cleanup archive | `archive/20250608_psf_cleanup/` |
| Report | `reports/PSF_CALIBRATION_20250605_SUMMARY.md` |

## Formal Preflight

```powershell
matlab -batch "run('D:/GMM_2_Final/Thesis_MOSR_Evidence/LabSystem_MOSR/psf_calibration/scripts/preflight_lab_inner_circle_roi_standard_fit.m')"
```

## Formal Run Command

```powershell
matlab -batch "run('D:/GMM_2_Final/Thesis_MOSR_Evidence/LabSystem_MOSR/psf_calibration/scripts/run_lab_inner_circle_roi_fine_prealign_fit.m')"
```

## Interpretation Rule

Only the copied Whole-FOV fitter on the prepared inner-circle ROI batch is the
formal PSF calibration path. The current BADS candidate is the fine
pre-alignment run. Archived full-frame, edge-derived, and superseded first-fit
outputs are traceability material, not current training PSF inputs.
