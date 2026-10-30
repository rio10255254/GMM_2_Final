# Fine Pre-Alignment PSF Comparison

## Question

Check whether the previous BADS PSF being slightly worse than the Gaussian control was just a fitting accident.

## What Changed

- Same GT, same 25 ROI images, same copied Whole-FOV Zernike/BADS fitter.
- Standard run used pre-alignment step `0.25 px` and crop `257 px`.
- Fine run used pre-alignment step `0.10 px` and crop `385 px`.

## Result

- Fine run verdict: `validated`
- Standard BADS median edge RMSE: `0.101980767`
- Fine BADS median edge RMSE: `0.101789875`
- Fine vs standard edge change: `-0.187%`
- Standard BADS gap vs Gaussian: `9.447%`
- Fine BADS gap vs Gaussian: `9.242%`
- Standard PSF centroid span: `1.102 px`
- Fine PSF centroid span: `0.038 px`

## Interpretation

The fine run is slightly better than the standard BADS run on median edge RMSE, and it is much cleaner in PSF centroid consistency. However, the improvement is small and the Gaussian control is still lower in median edge RMSE. This means the earlier BADS-vs-Gaussian gap was not just a one-run accident caused by coarse pre-alignment.

## Decision

Use the fine-prealignment BADS PSF as the BADS candidate for the first lab data-generation comparison, while keeping the `3.5 px` Gaussian control as the competing PSF.

## Artifacts

- Fine PSF stack: `results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`
- Fine fit summary: `results/20250605_inner_circle_roi_fine_prealign_fit/fit_summary.json`
- Fine validation summary: `results/20250605_inner_circle_roi_fine_prealign_validation/validation_summary.json`
- Fine forward comparison: `results/20250605_inner_circle_roi_fine_prealign_validation/forward_model_comparison_contact.png`
- Numeric comparison: `results/20250605_inner_circle_roi_fine_prealign_fit/standard_vs_fine_comparison.json`
