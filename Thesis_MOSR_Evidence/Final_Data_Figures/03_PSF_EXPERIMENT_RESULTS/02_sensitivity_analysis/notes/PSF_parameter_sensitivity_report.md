# PSF Parameter Sensitivity Analysis

- Generated: 2026-07-07T23:17:32
- Baseline: Circle_Round1 formal L0, 9 FOV points, each represented by the median of 15 repeated fits.
- Perturbation: one parameter at a time, up to 10% of its current search range, clipped to the current bounds.
- Shape metric: normalized PSF RMSE divided by the baseline normalized PSF peak.
- Absolute metric: fitted PSF image RMSE divided by the baseline fitted PSF peak; this includes AC amplitude.

## Model verification

- Python PSF builder vs saved MATLAB stack: RMSE=3.469e-19, max_abs=5.204e-18, relative RMSE to peak=5.522e-17.

## Top shape drivers

| Rank | Parameter | Status | Median shape change (% peak) | Centroid shift (px) | Width change (%) |
|---:|---|---|---:|---:|---:|
| 1 | x7 -> Z8 coma Y | dead | 0.140 | 0.1093 | 0.003 |
| 2 | x8 -> Z9 coma X | dead | 0.139 | 0.1089 | 0.002 |
| 3 | x12 -> Z13 spherical | trustworthy | 0.029 | 0.0029 | 0.290 |
| 4 | x4 -> Z5 defocus | trustworthy | 0.025 | 0.0025 | 0.252 |
| 5 | x5 -> Z6 astig 0deg | dead | 0.002 | 0.0002 | 0.001 |
| 6 | x3 -> Z4 astig 45deg | trustworthy | 0.002 | 0.0002 | 0.001 |

## Top absolute-image drivers

| Rank | Parameter | Status | Median absolute change (% peak) | Notes |
|---:|---|---|---:|---|
| 1 | x15 -> AC amplitude | trustworthy | 0.334 | scale-only amplitude driver |
| 2 | x7 -> Z8 coma Y | dead | 0.140 | shape/structure driver |
| 3 | x8 -> Z9 coma X | dead | 0.139 | shape/structure driver |
| 4 | x12 -> Z13 spherical | trustworthy | 0.029 | shape/structure driver |
| 5 | x4 -> Z5 defocus | trustworthy | 0.025 | shape/structure driver |
| 6 | x5 -> Z6 astig 0deg | dead | 0.002 | shape/structure driver |

## Output files

- shape_rank_png: `parameter_shape_sensitivity_rank.png`
- absolute_rank_png: `parameter_absolute_sensitivity_rank.png`
- shape_heatmap_png: `parameter_shape_sensitivity_heatmap.png`
- top_diff_maps_png: `top_parameter_diff_maps_fov061.png`
- Summary table: `parameter_sensitivity_summary.csv`
- Detail table: `parameter_sensitivity_detail.csv`

## Presentation interpretation

- Use the shape-sensitivity ranking to explain which optical parameters materially change the fitted PSF shape.
- Use the absolute-image ranking only when discussing amplitude/scale; otherwise x15 can dominate unfairly.
- Locked tilt parameters should show zero shape impact under the current pipeline because the fitter sets tilt to zero when generating PSF.
- Boundary-saturated parameters can still have physical PSF impact; this analysis separates impact from trustworthiness.