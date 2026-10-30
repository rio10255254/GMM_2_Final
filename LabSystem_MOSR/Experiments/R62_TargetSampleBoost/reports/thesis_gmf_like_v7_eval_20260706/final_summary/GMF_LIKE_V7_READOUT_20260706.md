# GMF-like displacement readout - R62 V7 short candidate

This uses the open in-repo GMF-like Gaussian template fit, not the external GMF scorer.

## Gap <= 30 s stability table

| group | best | Raw std um | R61 std um | V7 std um | V7 vs Raw | V7 vs R61 | Raw step um | R61 step um | V7 step um | valid |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| x_1um | raw | 0.01171 | 0.03783 | 0.33268 | 2741.9% | 779.5% | 1.00529 | 1.01169 | 0.59649 | True |
| x_0p5um | raw | 0.00974 | 0.03249 | 0.03980 | 308.8% | 22.5% | 0.50332 | 0.50565 | 0.50366 | True |
| 20x_1um | r61 | 0.08225 | 0.03984 | 0.04038 | -50.9% | 1.4% | 1.00436 | 1.01295 | 1.01415 | True |
| 20x_0p5um | v7 | 0.16320 | 0.14919 | 0.14844 | -9.0% | -0.5% | 0.50141 | 0.50055 | 0.50095 | True |
| 5x_1um | v7 | 0.44360 | 0.39375 | 0.39056 | -12.0% | -0.8% | 0.88260 | 0.84643 | 0.85649 | True |
| 5x_0p5um | raw | 0.11368 | 0.11883 | 0.12323 | 8.4% | 3.7% | 0.12108 | 0.49649 | 0.49246 | False |

## Plain readout

- V7 is more stable than Raw in 3/6 groups by this GMF-like metric.
- V7 is more stable than R61 v16 in 2/6 groups by this GMF-like metric.
- This metric is closer to local fitted-pattern positioning than the phase method, so it is more sensitive to boundary/shape reconstruction changes.
- If a row has valid=False, the median measured step is too far from the commanded step and should not be used as evidence.

## Files

- Per-step data: gmf_like_steps_with_gaps.csv
- Summary table: gmf_like_summary.csv
- Comparison table: gmf_like_raw_r61_v7_gap30_comparison.csv
- Stability plot: gmf_like_gap30_stability_um.png
- Step plot: gmf_like_gap30_step_um.png
