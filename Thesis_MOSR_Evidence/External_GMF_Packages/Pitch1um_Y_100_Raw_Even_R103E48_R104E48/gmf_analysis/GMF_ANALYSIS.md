# Pitch1um_Y_100 external GMF analysis

## Scope

The score files contain frame_0001 through frame_0100 for all three arms. The package frame_0000 coordinate is absent from the external output, so all step statistics use the common 100 coordinates and 99 consecutive steps only.

Coordinates are reported in GMF pixels. No physical-unit conversion is applied because this package does not carry a verified pixel calibration.

## Arm summary

Expected Y step: `-8.000 px`

| Arm | Coordinates | Missing | Score median | Scale median | Step median (px) | Step SD (px) | Y-step median (px) | Y-step SD (px) | Within 20% | Within 25% | Within 30% |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pitch1um_y100_raw | 100 | 0 | 79.110 | 1.001060 | 9.258 | 5.647 | -7.280 | 6.699 | 0.212 | 0.263 | 0.283 |
| pitch1um_y100_r103_e48 | 100 | 0 | 76.982 | 1.001270 | 11.267 | 5.514 | -7.560 | 6.894 | 0.192 | 0.202 | 0.283 |
| pitch1um_y100_r104_e48 | 100 | 0 | 78.640 | 1.002065 | 11.670 | 5.921 | -7.640 | 8.160 | 0.141 | 0.172 | 0.202 |

## Pairwise results

| Reference | Target | Median coordinate offset (px) | Offset drift slope Y (px/frame) | Median step-vector difference (px) | P95 step-vector difference (px) | Step magnitude SD ratio | Y-step SD ratio | Score median change |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| pitch1um_y100_raw | pitch1um_y100_r103_e48 | 21.531 | 0.004456 | 10.917 | 23.619 | 0.976 | 1.029 | -2.026 |
| pitch1um_y100_raw | pitch1um_y100_r104_e48 | 12.375 | 0.024500 | 10.335 | 28.113 | 1.049 | 1.218 | -0.239 |
| pitch1um_y100_r103_e48 | pitch1um_y100_r104_e48 | 17.632 | 0.020044 | 12.973 | 24.428 | 1.074 | 1.184 | 1.711 |

## Image parity check

- R103 E48 exact pixel-equal frames to Raw: 0/101
- R104 E48 exact pixel-equal frames to Raw: 101/101

## Caveats

- The missing first GMF coordinate is a file-output omission common to all three arms; it is not filled in or counted as a model failure.
- Raw is used as the paired reference for repeatability. This tests consistency relative to Raw, not independent absolute stage truth.
- Score Diff values are shown for diagnostics only because no locked acceptance threshold was included with this package.
- If an arm is pixel-identical to Raw but its GMF coordinates differ, that difference is a GMF run/template/repeatability issue, not an image-reconstruction effect; rerun both arms with the same locked GMF state before attributing it to the model.
