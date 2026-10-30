# R62 no-AMP candidate validation

This report compares Raw, R61 v16, old R62 target-boost, and two no-AMP R62 candidates on the same real displacement folders.

## Primary ROI, normal time gaps

| dataset | group | Raw std | R61 std | old R62 std | noAMP 8-step std | noAMP 2e200 std | noAMP 8 vs R61 | noAMP 2e200 vs R61 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 20260702_100MG | x_0p5um | 0.0895 | 0.0882 | 0.0882 | 0.0907 | 0.0906 | 2.8% | 2.8% |
| 20260702_100MG | x_1um | 0.1274 | 0.1105 | 0.1105 | 0.1114 | 0.1047 | 0.8% | -5.3% |
| 20260704_20x_5x | 20x_0p5um | 0.2060 | 0.2059 | 0.2059 | 0.2066 | 0.2066 | 0.3% | 0.4% |
| 20260704_20x_5x | 20x_1um | 0.1280 | 0.1411 | 0.1411 | 0.1403 | 0.1347 | -0.5% | -4.5% |
| 20260704_20x_5x | 5x_0p5um | 0.0164 | 0.0138 | 0.0138 | 0.0132 | 0.0124 | -4.9% | -10.5% |
| 20260704_20x_5x | 5x_1um | 0.2359 | 0.1996 | 0.1996 | 0.2001 | 0.2005 | 0.2% | 0.4% |

## Robust IQR subset, primary ROI

| dataset | group | R61 std | noAMP 8-step std | noAMP 2e200 std | noAMP 8 vs R61 | noAMP 2e200 vs R61 |
|---|---|---:|---:|---:|---:|---:|
| 20260702_100MG | x_0p5um | 0.0882 | 0.0907 | 0.0906 | 2.8% | 2.8% |
| 20260702_100MG | x_1um | 0.0904 | 0.0821 | 0.0763 | -9.2% | -15.6% |
| 20260704_20x_5x | 20x_0p5um | 0.0625 | 0.0621 | 0.0634 | -0.6% | 1.5% |
| 20260704_20x_5x | 20x_1um | 0.0551 | 0.0552 | 0.0540 | 0.1% | -2.0% |
| 20260704_20x_5x | 5x_0p5um | 0.0138 | 0.0132 | 0.0103 | -4.9% | -25.3% |
| 20260704_20x_5x | 5x_1um | 0.1718 | 0.1727 | 0.1750 | 0.6% | 1.9% |

## Files

- Step table: candidate_displacement_steps.csv
- Summary table: candidate_displacement_summary.csv
- Comparison table: candidate_primary_comparison.csv
- Main plot: candidate_primary_stability.png
