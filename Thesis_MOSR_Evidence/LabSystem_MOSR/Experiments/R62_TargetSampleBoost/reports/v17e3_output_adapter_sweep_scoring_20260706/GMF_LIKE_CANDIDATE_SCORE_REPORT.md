# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | v17e3_detail035 | -1.913 | 0.671 | 2 | -14.390 | -76.302 |
| 2 | v17e3_detail010 | -0.516 | -2.429 | 3 | -5.806 | -96.323 |
| 3 | v17e3_detail020 | -2.060 | -3.034 | 3 | -7.493 | -99.553 |
| 4 | v17e3_blend025 | -2.079 | -2.997 | 3 | -8.858 | -100.937 |
| 5 | v17e3_blend050 | -3.222 | -4.860 | 3 | -11.408 | -104.630 |
| 6 | r61 | -796.142 | -73.673 | 4 | -124.846 | -1040.987 |
| 7 | v7 | -801.780 | -72.986 | 4 | -124.958 | -1046.737 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | v17e3_blend050 |
| 20260702_100MG | x_1um | primary | raw |
| 20260704_20x_5x | 20x_0p5um | guardrail | v17e3_blend050 |
| 20260704_20x_5x | 20x_1um | guardrail | v17e3_blend025 |
| 20260704_20x_5x | 5x_0p5um | guardrail | v17e3_detail035 |
| 20260704_20x_5x | 5x_1um | guardrail | raw |
