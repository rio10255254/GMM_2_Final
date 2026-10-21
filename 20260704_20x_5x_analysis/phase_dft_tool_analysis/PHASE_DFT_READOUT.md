# 20260704 20x/5x phase DFT analysis

ROI: x=560, y=80, width=1460, height=1420. Gaps above 30 s are excluded in the primary summary.

## Primary gap-filtered comparison

| group | image | steps | nominal um | median step um | std um | median abs error um | median y drift um |
|---|---|---:|---:|---:|---:|---:|---:|
| 20x_1um | R61 v16 PSF-off | 48 | 1.000 | 1.010850 | 0.023939 | 0.011713 | 0.010350 |
| 20x_1um | Raw | 48 | 1.000 | 1.061737 | 0.031669 | 0.062600 | 0.018975 |
| 20x_0p5um | R61 v16 PSF-off | 48 | 0.500 | 0.507150 | 0.034822 | 0.010600 | 0.008625 |
| 20x_0p5um | Raw | 48 | 0.500 | 0.017250 | 0.172070 | 0.482750 | 0.003450 |
| 5x_1um | R61 v16 PSF-off | 43 | 1.000 | 0.848700 | 0.137712 | 0.185800 | 0.006900 |
| 5x_1um | Raw | 43 | 1.000 | 0.179400 | 0.210865 | 0.820600 | 0.006900 |
| 5x_0p5um | R61 v16 PSF-off | 45 | 0.500 | 0.572700 | 0.008722 | 0.072700 | 0.006900 |
| 5x_0p5um | Raw | 45 | 0.500 | 0.124200 | 0.004532 | 0.375800 | 0.006900 |

## Raw vs R61 v16

| group | Raw median | R61 median | Raw std | R61 std | std change | Raw error | R61 error |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20x_1um | 1.061737 | 1.010850 | 0.031669 | 0.023939 | -24.4% | 0.062600 | 0.011713 |
| 20x_0p5um | 0.017250 | 0.507150 | 0.172070 | 0.034822 | -79.8% | 0.482750 | 0.010600 |
| 5x_1um | 0.179400 | 0.848700 | 0.210865 | 0.137712 | -34.7% | 0.820600 | 0.185800 |
| 5x_0p5um | 0.124200 | 0.572700 | 0.004532 | 0.008722 | +92.5% | 0.375800 | 0.072700 |

## Files
- phase_dft_summary_enriched.csv
- phase_dft_raw_vs_v16_gap30_comparison.csv
- phase_dft_all_steps_enriched.csv
- phase_dft_largest_errors.csv
- phase_dft_gap30_summary_bars.png