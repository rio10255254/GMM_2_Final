# L0 New-Data Noise Floor Report - Circle_Round1

- Generated: 2026-07-07T23:18:02
- Trials: 15
- FOV points: 9 (1, 6, 11, 56, 61, 66, 111, 116, 121)
- Data rule: 11x11, 2 frames/position, using frame 1
- Repeat rule: Circle_Round1/2/3 are capture repeats; two frames per position are duplicate frames
- Target: circle_boundary_only
- Center block handling: filled_in_prepared_inputs_and_excluded_by_circle_edge_mask
- Source JSON: L0_newdata_noise_floor.json

## Main Readout

- Clean noise floor median: 0.027055 (mean 0.065377)
- Trustworthy coefficients: 6/15
- FOV clean-noise consistency max/min: 1.211
- Fit value range: 13404.27 to 16671.73; mean 14952.42

## FOV Clean Noise

| FOV | Clean std | Full mean std |
|---|---:|---:|
| #1 (row 1, col 1) | 0.074801 | 0.062517 |
| #6 (row 1, col 6) | 0.065286 | 0.057253 |
| #11 (row 1, col 11) | 0.064420 | 0.057111 |
| #56 (row 6, col 1) | 0.063969 | 0.056104 |
| #61 (row 6, col 6) | 0.066505 | 0.056647 |
| #66 (row 6, col 11) | 0.065099 | 0.055724 |
| #111 (row 11, col 1) | 0.062591 | 0.054640 |
| #116 (row 11, col 6) | 0.061746 | 0.054928 |
| #121 (row 11, col 11) | 0.063977 | 0.056601 |

## Coefficient Classification

| Coefficient | Status | Overall std | Bound % | Reason |
|---|---|---:|---:|---|
| x1 -> Z2 Y-tilt (locked=0) | locked | 0.215087 | 14.8% | tilt is locked by the fitter, so this coefficient is not a useful noise-floor source |
| x2 -> Z3 X-tilt (locked=0) | locked | 0.191718 | 13.3% | tilt is locked by the fitter, so this coefficient is not a useful noise-floor source |
| x3 -> Z4 astig 45deg | trustworthy | 0.048561 | 3.7% | values vary inside the search range |
| x4 -> Z5 defocus | trustworthy | 0.277748 | 17.0% | values vary inside the search range |
| x5 -> Z6 astig 0deg | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x6 -> Z7 trefoil | bound_saturated | 0.034146 | 99.3% | most values sit on the search boundary |
| x7 -> Z8 coma Y | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x8 -> Z9 coma X | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x9 -> Z10 trefoil | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x10 -> Z11 quadrafoil | trustworthy | 0.008098 | 48.9% | values vary inside the search range |
| x11 -> Z12 secondary astig | trustworthy | 0.006465 | 23.0% | values vary inside the search range |
| x12 -> Z13 spherical | trustworthy | 0.029503 | 0.0% | values vary inside the search range |
| x13 -> Z14 secondary astig | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x14 -> Z15 quadrafoil | bound_saturated | 0.006823 | 99.3% | most values sit on the search boundary |
| x15 -> AC amplitude | trustworthy | 0.026750 | 62.2% | values vary inside the search range |

## Notes

- This is a within-capture repeated-fit readout on one capture round.
- For the corrected experiment definition, Circle_Round1 is the formal L0 anchor; Circle_Round2/3 are L1 source diagnostics.
- Circle_Round1/2/3 are handled as the three capture repeats; the paired frames inside each position are not the main repeat axis here.
- The square blocks at the center are excluded by the fitting mask, so the circle boundary controls the fit.