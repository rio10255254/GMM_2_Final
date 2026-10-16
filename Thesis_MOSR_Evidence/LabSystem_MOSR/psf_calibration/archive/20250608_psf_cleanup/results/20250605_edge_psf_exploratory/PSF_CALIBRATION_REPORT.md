# Lab System PSF Calibration Report

## Scope

This report is the first PSF calibration pass for the lab-system MOSR line.
It uses sharp black-white calibration target edges to estimate an edge-derived
isotropic Gaussian PSF across the field of view.

## Results

- Source images: 25
- Usable edge profiles: 17500
- Median sigma: 3.4018 px
- Median FWHM: 8.0105 px
- Sigma p10-p90: 3.2105 to 3.6554 px
- Empty FOV tiles filled from global median: 0

## Generated Files

- `lab_edge_gaussian_psf_10x10.mat`: MATLAB PSF package with `psf_grid`.
- `sigma_heatmap.png`: FOV tile map of estimated blur width.
- `sigma_histogram.png`: distribution of accepted edge-profile estimates.
- `representative_edge_profiles.png`: sampled edge-spread profiles.
- `edge_profiles.csv`, `tile_summary.csv`, `image_summary.csv`: detailed tables.

## Interpretation

This output is an initial lab-system PSF proxy, not yet the final training PSF.
It is meant to establish the separated LabSystem_MOSR calibration flow and
give a measurable first target for follow-up validation.
