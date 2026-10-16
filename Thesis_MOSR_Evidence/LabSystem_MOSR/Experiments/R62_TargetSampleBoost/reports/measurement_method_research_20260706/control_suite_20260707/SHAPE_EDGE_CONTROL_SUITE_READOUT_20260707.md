# Shape-Edge Control Suite Readout 20260707

This suite checks two thesis-defense risks:

1. Negative controls: the method should fail or return zero when motion is absent/invalid.
2. Expected-step bias: the method should not simply output the supplied 1um prior.

All real-data cases use the same 100MG x_1um ROI:

`x=1010, y=35, width=900, height=650`

The main statistics use all attempted steps. High-confidence coverage is reported separately.

| case | attempted | high-conf | coverage % | mean step um | std um | true error um | interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| positive_v31_nominal | 49 | 49 | 100.0 | 1.005682 | 0.010178 | 0.005682 | PASS: recovered true motion without special expected-step dependence |
| positive_v31_wide_zero_center | 49 | 49 | 100.0 | 1.005682 | 0.010178 | 0.005682 | PASS: recovered true motion without special expected-step dependence |
| positive_v31_wide_wrong_direction_center | 49 | 49 | 100.0 | 1.005682 | 0.010178 | 0.005682 | PASS: recovered true motion without special expected-step dependence |
| wrong_direction_v31_narrow | 49 | 0 | 0.0 | 1.200600 | 0.000000 | 0.200600 | PASS: wrong expected motion was rejected |
| wrong_step_v31_narrow_0p5um | 49 | 0 | 0.0 | 0.634800 | 0.000000 | 0.365200 | PASS: wrong expected motion was rejected |
| no_motion_duplicate_v31_expected_zero | 49 | 49 | 100.0 | 0.000000 | 0.000000 | 0.000000 | PASS: zero-motion control measured as zero |
| no_motion_duplicate_v31_expected_1um | 49 | 0 | 0.0 | 0.793500 | 0.000000 | 0.793500 | PASS: zero-motion control was not accepted as nonzero motion |
| blank_expected_1um | 9 | 0 | 0.0 | 0.000000 | 0.000000 |  | PASS: invalid control mostly rejected |
| shuffled_v31_expected_1um | 49 | 0 | 0.0 | 0.798288 | 0.033514 |  | PASS: invalid control mostly rejected |
| raw_nominal | 49 | 16 | 32.7 | 0.886481 | 0.092068 | 0.113519 | CHECK: control does not cleanly support the expected behavior |
| raw_wide_zero_center | 49 | 16 | 32.7 | 0.878595 | 0.120664 | 0.121405 | CHECK: control does not cleanly support the expected behavior |

## Readout

- The duplicate-frame controls verify that the method can return zero motion and does not accept identical frames as 1um motion.
- The blank control verifies that an ROI without edges fails instead of returning a fake displacement.
- The shuffled control verifies that broken frame order does not look like stable consecutive 1um motion.
- The wide-search V31 controls verify that the 1um answer is recovered even when the expected-step center is zero or the wrong direction, as long as the true motion is inside the search window.
- The narrow wrong-direction and wrong-step controls verify that a wrong prior does not get accepted as a valid high-confidence answer.

## Evidence Files

- `control_suite_summary.csv`: one-row summary for every control case.
- `*_steps.csv`: per-step displacement and confidence details.
- `*_summary.json`: full machine-readable settings and statistics for each case.
