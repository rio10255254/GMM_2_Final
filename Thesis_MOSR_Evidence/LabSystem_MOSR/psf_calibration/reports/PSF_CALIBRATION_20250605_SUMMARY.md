# PSF Calibration Summary

## Purpose

This note starts the independent lab-system MOSR line. It does not change the
original industry-project baseline. The formal PSF calibration path now reuses
the original project Whole-FOV Zernike/BADS fitter copied into this lab area.

The `20250605_PSF_Calibration` image batch has 25 measured lab captures. The
image filenames show the capture date as 2026-06-05.

## Formal Status

The usable formal path for this lab data is the prepared inner-circle ROI batch.
The full 2048x1536 chart images include outer rings, text, markers, and frame
cuts that would contaminate the fit, so the earlier full-frame staging has been
archived.

- Measurement images staged: 25
- Formal input folder: `inputs/20250605_inner_circle_roi/measured`
- Formal runner: `scripts/run_lab_inner_circle_roi_fine_prealign_fit.m`
- Copied standard fitter: `scripts/standard_wholefov/`
- Superseded material archive: `archive/20250608_psf_cleanup/`

Do not use the original industry-project GT unless it is physically the correct
clean target for the lab captures.

## Prepared Lab ROI

The lab setup is Basler acA2040-120um with a 20x objective, no relay
magnification, no binning, and no software scaling. The effective scale is
`0.1725 um/px`, so the usable `phi 0.1 mm` inner white disk is `579.71 px` in
the sharp GT.

- ROI config: `configs/inner_circle_roi_fine_prealign_20250608.json`
- ROI GT: `inputs/20250605_inner_circle_roi/GT/LAB_INNER_CIRCLE_GT_901.bmp`
- ROI images: `inputs/20250605_inner_circle_roi/measured`
- ROI overlay check: `results/20250605_inner_circle_roi/inner_circle_roi_gt_overlay_contact.png`
- ROI runner: `scripts/run_lab_inner_circle_roi_fine_prealign_fit.m`

## Formal ROI Fit Result

The copied Whole-FOV Zernike/BADS fitter completed on all 25 ROI images. The
current formal BADS candidate is the fine pre-alignment run.

- PSF output: `results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`
- Batch result table: `results/20250605_inner_circle_roi_fine_prealign_fit/batch_results.csv`
- Fit summary: `results/20250605_inner_circle_roi_fine_prealign_fit/fit_summary.json`
- PSF contact sheet: `results/20250605_inner_circle_roi_fine_prealign_fit/psf_contact_sheet.png`
- PSF stack shape: `101 x 101 x 5 x 5`
- Total fit time recorded by MATLAB: `919.93 s`
- Median per-image fit time: `33.70 s`
- Median iterations: `494`
- Median objective value: `5033.18`

Basic sanity checks passed: all 25 images produced a result, no stderr error was
recorded, and the fitted PSFs are centered and visually consistent across the
5x5 field.

## Validation Result

The formal ROI PSF fit was validated with forward-model reconstruction against
the measured ROI images.

- Validation verdict: `validated`
- Validation report: `results/20250605_inner_circle_roi_fine_prealign_validation/VALIDATION_REPORT.md`
- Forward-model comparison: `results/20250605_inner_circle_roi_fine_prealign_validation/forward_model_comparison_contact.png`
- PSF consistency map: `results/20250605_inner_circle_roi_fine_prealign_validation/psf_consistency_map.png`
- BADS vs sharp GT edge improvement: `51.99%`
- BADS vs global Gaussian edge gap: `9.24%`
- Best global Gaussian control sigma: `3.5 px`

Next action has been advanced to lab data generation planning. Because the
Gaussian control is slightly better on median edge RMSE, the next round should
compare the formal BADS PSF against the Gaussian control before selecting a
single training PSF.

## Superseded First BADS Fit

The first 25-image BADS fit was archived after the fine pre-alignment run
proved slightly better and much more centroid-stable. It is retained as
comparison evidence, not as a current training PSF input.

- Fine comparison report: `reports/FINE_PREALIGN_COMPARISON_20250608.md`
- Archived first PSF output: `archive/20250608_psf_cleanup/results/20250605_inner_circle_roi_standard_fit_superseded_by_fine/PSF_fitted_2D_FOVstack.mat`
- Archived first validation: `archive/20250608_psf_cleanup/results/20250605_inner_circle_roi_validation_superseded_by_fine/VALIDATION_REPORT.md`
- Pre-alignment step: `0.10 px` instead of `0.25 px`
- Pre-alignment crop: `385 px` instead of `257 px`
- Fine BADS median edge RMSE: `0.101789875`
- Standard BADS median edge RMSE: `0.101980767`
- Fine BADS gap vs Gaussian: `9.24%`
- Standard BADS gap vs Gaussian: `9.45%`
- Fine PSF centroid span: `0.038 px`
- Standard PSF centroid span: `1.102 px`

The fine run is slightly better and much more centroid-stable, so it should be
used as the BADS candidate for the first lab data-generation comparison. The
first BADS fit has been moved out of the active result area. The fine run still
does not beat the `3.5 px` Gaussian control on median edge RMSE, so the Gaussian
control must remain in the next comparison.

## Archived Exploratory Result

The earlier edge-derived Gaussian first pass is archived only as an exploratory
sanity check:

- Raw images used: 25
- Accepted edge profiles: 17,500
- FOV grid: 10x10
- Empty FOV tiles: 0
- Median sigma: 3.4018 px
- Median FWHM: 8.0105 px
- Sigma p10-p90 range: 3.2105 to 3.6554 px

The archived exploratory PSF package is:

`archive/20250608_psf_cleanup/results/20250605_edge_psf_exploratory/lab_edge_gaussian_psf_10x10.mat`

## Inspection

The archived output figures are:

- `archive/20250608_psf_cleanup/results/20250605_edge_psf_exploratory/sigma_heatmap.png`
- `archive/20250608_psf_cleanup/results/20250605_edge_psf_exploratory/sigma_histogram.png`
- `archive/20250608_psf_cleanup/results/20250605_edge_psf_exploratory/representative_edge_profiles.png`

The heatmap shows a smooth spatial pattern rather than random tile noise. The
representative edge profiles show a stable edge-spread curve. This made it
useful as a sanity check, but it is not the formal PSF for lab training.

## Limitation

This exploratory output is not the formal PSF fitting result. The formal BADS
candidate is the validated fine pre-alignment inner-circle ROI fit from the
copied Whole-FOV fitter.
