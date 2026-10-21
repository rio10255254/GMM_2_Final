# L1 New-Data Capture Repeatability Summary

- Generated: 2026-07-07T23:18:10
- Result: within_L0_floor - The three capture rounds stay inside the repeated-fit floor by the main readout.
- Capture repeat axis: Circle_Round1, Circle_Round2, Circle_Round3.
- Formal L0 anchor: Circle_Round1 only.
- Within each capture round: 15 repeated fits are collapsed by median before cross-round comparison.
- Frame policy: uses frame 1 from each two-frame position pair; the second frame is not treated as a fourth/fifth/sixth L1 repeat.
- Fit target: circle boundary only; the center square blocks are masked.
- Guardrail: this is an L1 validation readout, not a formal baseline promotion.

## Main Readout

- Readout coefficients: 6 (x3 -> Z4 astig 45deg, x4 -> Z5 defocus, x10 -> Z11 quadrafoil, x11 -> Z12 secondary astig, x12 -> Z13 spherical, x15 -> AC amplitude)
- Repeat-fit floor median: 0.027055
- L1 capture spread median: 0.004086
- Net L1 spread after repeat-fit floor: 0.000000
- Median capture/repeat-fit ratio: 0.044
- 95th percentile capture/repeat-fit ratio: 0.822
- Max capture/repeat-fit ratio: 2.090

## Input Check

- Grid: 11x11
- FOV points: 1, 6, 11, 56, 61, 66, 111, 116, 121
- Frames per position in source captures: 2
- Main frame used for this L1 readout: frame 1
- Target policy: circle_boundary_only
- Center block policy: filled_in_prepared_inputs_and_excluded_by_circle_edge_mask

## Source Rounds

| Round | Repeated fits | Role | Repeat-fit median | Repeat-fit mean | Mean fit value | Result rows |
|---|---:|---|---:|---:|---:|---:|
| Circle_Round1 | 15 | formal_L0_anchor | 0.027055 | 0.065377 | 14952.42 | 135 |
| Circle_Round2 | 15 | L1_source_diagnostic | 0.022559 | 0.051162 | 14993.76 | 135 |
| Circle_Round3 | 15 | L1_source_diagnostic | 0.027294 | 0.058550 | 14793.45 | 135 |

## FOV Readout

| FOV | Repeat-fit floor median | L1 spread median | Net L1 spread | Median capture/repeat-fit ratio |
|---|---:|---:|---:|---:|
| #1 (row 1, col 1) | 0.040821 | 0.007471 | 0.000000 | 0.058 |
| #6 (row 1, col 6) | 0.020864 | 0.003451 | 0.000000 | 0.028 |
| #11 (row 1, col 11) | 0.019594 | 0.013330 | 0.000000 | 0.058 |
| #56 (row 6, col 1) | 0.019651 | 0.007600 | 0.000000 | 0.058 |
| #61 (row 6, col 6) | 0.020008 | 0.005639 | 0.000000 | 0.073 |
| #66 (row 6, col 11) | 0.018017 | 0.005262 | 0.000000 | 0.207 |
| #111 (row 11, col 1) | 0.017223 | 0.001787 | 0.000000 | 0.022 |
| #116 (row 11, col 6) | 0.016671 | 0.002498 | 0.000000 | 0.050 |
| #121 (row 11, col 11) | 0.020164 | 0.003860 | 0.000000 | 0.034 |

## Coefficient Readout

| Coefficient | Used | Trustworthy rounds | Repeat-fit floor median | L1 spread median | Net L1 spread | Median capture/repeat-fit ratio |
|---|---:|---:|---:|---:|---:|---:|
| x1 -> Z2 Y-tilt (locked=0) | no | 0/3 | 0.214558 | 0.123834 | 0.000000 | 0.368 |
| x2 -> Z3 X-tilt (locked=0) | no | 0/3 | 0.211284 | 0.061432 | 0.000000 | 0.126 |
| x3 -> Z4 astig 45deg | yes | 3/3 | 0.041389 | 0.005864 | 0.000000 | 0.042 |
| x4 -> Z5 defocus | yes | 3/3 | 0.251677 | 0.069662 | 0.000000 | 0.160 |
| x5 -> Z6 astig 0deg | no | 0/3 | 0.000000 | 0.000000 | 0.000000 | 0.000 |
| x6 -> Z7 trefoil | no | 0/3 | 0.025820 | 0.000000 | 0.000000 | 0.000 |
| x7 -> Z8 coma Y | no | 0/3 | 0.000000 | 0.000000 | 0.000000 | 0.000 |
| x8 -> Z9 coma X | no | 0/3 | 0.000000 | 0.000000 | 0.000000 | 0.000 |
| x9 -> Z10 trefoil | no | 0/3 | 0.000000 | 0.000000 | 0.000000 | 0.000 |
| x10 -> Z11 quadrafoil | yes | 3/3 | 0.007013 | 0.000637 | 0.000000 | 0.011 |
| x11 -> Z12 secondary astig | yes | 3/3 | 0.004677 | 0.002625 | 0.000000 | 0.244 |
| x12 -> Z13 spherical | yes | 3/3 | 0.030869 | 0.015611 | 0.000000 | 0.322 |
| x13 -> Z14 secondary astig | no | 0/3 | 0.000000 | 0.000000 | 0.000000 | 0.000 |
| x14 -> Z15 quadrafoil | no | 0/3 | 0.005164 | 0.000000 | 0.000000 | 0.000 |
| x15 -> AC amplitude | yes | 3/3 | 0.004234 | 0.000446 | 0.000000 | 0.025 |

## Interpretation

- The three capture rounds stay inside the repeated-fit floor by the main readout.
- Because there are only three capture rounds, this should be treated as an L1 measurement of this sample/capture condition.
- The paired second image at each position is available for a separate paired-frame check, but it is not part of the main L1 repeat axis used here.