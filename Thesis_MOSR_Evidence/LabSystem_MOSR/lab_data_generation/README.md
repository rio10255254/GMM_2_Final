# Lab Data Generation Legacy Note

This folder is now kept only as the old planning note for lab-system data
generation.

The formal lab training-data root is now:

`../Training_Data/`

That name is intentional because it mirrors the main project's
`Training_Data/` layout.

The fine pre-alignment PSF validation verdict is `validated`. It is the cleaner
BADS candidate because it is slightly better than the first BADS fit and much
more stable in PSF center. The validation still showed that a single global
Gaussian control is slightly better on median edge RMSE. Therefore the next lab
data generation plan should keep both PSF inputs:

- formal copied-fitter BADS PSF: `psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`
- Gaussian control: sigma `3.5 px`

The first data-generation round should compare both paths before using either
one as the only training PSF.
