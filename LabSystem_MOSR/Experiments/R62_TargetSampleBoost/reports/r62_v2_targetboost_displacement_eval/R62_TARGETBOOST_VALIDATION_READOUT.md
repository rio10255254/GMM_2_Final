# R62 target-sample-boost validation readout

This compares Raw, R61 v16, and R62 target-boost on the same displacement image folders.
The clean table excludes frame intervals with time gaps longer than 30 seconds.

## Primary stability comparison

| dataset | group | Raw std px | R61 std px | R62 std px | R62 vs Raw | R62 vs R61 | Raw median px | R61 median px | R62 median px |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20260702_100MG | x_0p5um | 0.0895 | 0.0882 | 0.0882 | -1.5% | 0.0% | 7.2481 | 7.2562 | 7.2562 |
| 20260702_100MG | x_1um | 0.1274 | 0.1105 | 0.1105 | -13.3% | 0.0% | 14.6084 | 14.5731 | 14.5731 |
| 20260704_20x_5x | 20x_0p5um | 0.2060 | 0.2059 | 0.2059 | -0.0% | 0.0% | 2.9093 | 2.8792 | 2.8792 |
| 20260704_20x_5x | 20x_1um | 0.1280 | 0.1411 | 0.1411 | 10.2% | -0.0% | 5.8600 | 5.8535 | 5.8535 |
| 20260704_20x_5x | 5x_0p5um | 0.0164 | 0.0138 | 0.0138 | -15.5% | -0.0% | 0.6577 | 0.7133 | 0.7133 |
| 20260704_20x_5x | 5x_1um | 0.2359 | 0.1996 | 0.1996 | -15.4% | -0.0% | 1.4615 | 1.3433 | 1.3433 |

## 20260704 physical-step check

| group | Raw error um | R61 error um | R62 error um | Raw median um | R61 median um | R62 median um |
|---|---:|---:|---:|---:|---:|---:|
| 20x_1um | 0.01086 | 0.00973 | 0.00973 | 1.01086 | 1.00973 | 1.00973 |
| 20x_0p5um | 0.00185 | 0.00334 | 0.00334 | 0.50185 | 0.49666 | 0.49666 |
| 5x_1um | 0.00846 | 0.07313 | 0.07313 | 1.00846 | 0.92687 | 0.92687 |
| 5x_0p5um | 0.04617 | 0.00782 | 0.00781 | 0.45383 | 0.49218 | 0.49219 |

## Initial interpretation

- R62 is a target-sample adaptation candidate. It should be judged by whether it helps these real sequences without breaking the old R61 behavior.
- The numbers above are internal image-registration checks, not an external GMF score.
- A lower std means the frame-to-frame measured displacement is more stable.
- The physical-step check is available only for the 20260704 folders because their magnification labels are explicit.

## Files

- Full per-step table: `r62_displacement_steps.csv`
- Summary table: `r62_displacement_summary.csv`
- Raw/R61/R62 comparison table: `r62_raw_r61_r62_comparison.csv`
- Main stability plot: `primary_stability_raw_r61_r62.png`
