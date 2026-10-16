# L0 New-Data Noise Floor Report - Circle_Round2

- Generated: 2026-07-07T23:18:03
- Trials: 15
- FOV points: 9 (1, 6, 11, 56, 61, 66, 111, 116, 121)
- Data rule: 11x11, 2 frames/position, using frame 1
- Repeat rule: Circle_Round1/2/3 are capture repeats; two frames per position are duplicate frames
- Target: circle_boundary_only
- Center block handling: filled_in_prepared_inputs_and_excluded_by_circle_edge_mask
- Source JSON: L0_newdata_noise_floor.json

## Main Readout

- Clean noise floor median: 0.022559 (mean 0.051162)
- Trustworthy coefficients: 6/15
- FOV clean-noise consistency max/min: 1.377
- Fit value range: 13341.05 to 17359.07; mean 14993.76

## FOV Clean Noise

| FOV | Clean std | Full mean std |
|---|---:|---:|
| #1 (row 1, col 1) | 0.064870 | 0.059382 |
| #6 (row 1, col 6) | 0.054615 | 0.054974 |
| #11 (row 1, col 11) | 0.050633 | 0.052820 |
| #56 (row 6, col 1) | 0.048389 | 0.050891 |
| #61 (row 6, col 6) | 0.048784 | 0.048635 |
| #66 (row 6, col 11) | 0.047101 | 0.048012 |
| #111 (row 11, col 1) | 0.048657 | 0.048650 |
| #116 (row 11, col 6) | 0.048434 | 0.048372 |
| #121 (row 11, col 11) | 0.048971 | 0.047877 |

## Coefficient Classification

| Coefficient | Status | Overall std | Bound % | Reason |
|---|---|---:|---:|---|
| x1 -> Z2 Y-tilt (locked=0) | locked | 0.212439 | 10.4% | tilt is locked by the fitter, so this coefficient is not a useful noise-floor source |
| x2 -> Z3 X-tilt (locked=0) | locked | 0.204311 | 10.4% | tilt is locked by the fitter, so this coefficient is not a useful noise-floor source |
| x3 -> Z4 astig 45deg | trustworthy | 0.036243 | 6.7% | values vary inside the search range |
| x4 -> Z5 defocus | trustworthy | 0.216502 | 6.7% | values vary inside the search range |
| x5 -> Z6 astig 0deg | bound_saturated | 0.000000 | 100.0% | most values sit on the search boundary |
| x6 -> Z7 trefoil | bound_saturated | 0.025302 | 97.0% | most values sit on the search boundary |
| x7 -> Z8 coma Y | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x8 -> Z9 coma X | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x9 -> Z10 trefoil | bound_saturated | 0.000001 | 100.0% | most values sit on the search boundary |
| x10 -> Z11 quadrafoil | trustworthy | 0.006077 | 56.3% | values vary inside the search range |
| x11 -> Z12 secondary astig | trustworthy | 0.005846 | 9.6% | values vary inside the search range |
| x12 -> Z13 spherical | trustworthy | 0.027191 | 0.0% | values vary inside the search range |
| x13 -> Z14 secondary astig | dead | 0.000000 | 100.0% | all trials converged to nearly the same value |
| x14 -> Z15 quadrafoil | bound_saturated | 0.005007 | 100.0% | most values sit on the search boundary |
| x15 -> AC amplitude | trustworthy | 0.023721 | 61.5% | values vary inside the search range |

## Notes

- This is a within-capture repeated-fit readout on one capture round.
- For the corrected experiment definition, Circle_Round1 is the formal L0 anchor; Circle_Round2/3 are L1 source diagnostics.
- Circle_Round1/2/3 are handled as the three capture repeats; the paired frames inside each position are not the main repeat axis here.
- The square blocks at the center are excluded by the fitting mask, so the circle boundary controls the fit.