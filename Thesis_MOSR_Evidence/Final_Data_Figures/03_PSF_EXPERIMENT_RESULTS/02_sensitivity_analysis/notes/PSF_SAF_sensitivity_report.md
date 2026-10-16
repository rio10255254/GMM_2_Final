# PSF SAF Sensitivity Analysis

- Generated: 2026-07-07T23:17:44
- Real MATLAB fitting code was used for coefficient evaluation through `HDR_fitting_2D_WholeFOV_candidate_prealign`.
- A focused FOV61 formal refit is also run through `HDR_fitting_2D_WholeFOV_reasonable_v1` as a real-BADS execution check.
- Sensitivity coefficient: `SC = (Y_plus - Y_minus) / (X_plus - X_minus)`.
- SAF: `((Y_plus - Y_minus) / Y0) / ((X_plus - X_minus) / X0)`.
- SAF is intentionally left as NA when the input or output baseline is effectively zero.

## Pure Parameter Result

| Rank | Parameter | Shape impact (% ideal peak) | SAF shape | SC shape |
|---:|---|---:|---:|---:|
| 1 | x8 -> Z9 coma X | 0.1383 | 1 | 13.8324 |
| 2 | x7 -> Z8 coma Y | 0.1383 | 1 | 13.8324 |
| 3 | x2 -> Z3 X-tilt | 0.0530 | 1 | 5.2949 |
| 4 | x1 -> Z2 Y-tilt | 0.0530 | 1 | 5.2949 |
| 5 | x12 -> Z13 spherical | 0.0022 | 1.68 | 0.3713 |
| 6 | x11 -> Z12 sec astig | 0.0008 | 1.78 | 0.1390 |
| 7 | x13 -> Z14 sec astig | 0.0008 | 1.8 | 0.1369 |
| 8 | x6 -> Z7 trefoil | 0.0003 | 1 | 0.0271 |

## Best-Fit Operating Result

| Rank | Parameter | Median abs SAF loss | Median local shape response (% fitted peak) | SAF-defined FOV count |
|---:|---|---:|---:|---:|
| 1 | x8 -> Z9 coma X | 0.0508 | 0.0697 | 9/9 |
| 2 | x7 -> Z8 coma Y | 0.0186 | 0.0699 | 9/9 |
| 3 | x5 -> Z6 astig 0deg | 0.00264 | 0.0009 | 9/9 |
| 4 | x13 -> Z14 sec astig | 0.00102 | 0.0003 | 9/9 |
| 5 | x9 -> Z10 trefoil | 2.05e-05 | 0.0001 | 9/9 |
| 6 | x12 -> Z13 spherical | 1.19e-05 | 0.0153 | 9/9 |
| 7 | x6 -> Z7 trefoil | 6.97e-06 | 0.0001 | 9/9 |
| 8 | x14 -> Z15 quadrafoil | 2.57e-06 | 0.0000 | 9/9 |

## Interpretation

- The pure-parameter view ranks physical PSF impact without using the current search bounds.
- The operating-point view tells which fitted coefficients the real loss is locally sensitive to near the best real BADS outputs.
- Parameters with zero or near-zero fitted values cannot have a standard SAF at the operating point; their local absolute response is still reported.
- AC amplitude should be interpreted as intensity scaling, not PSF shape.