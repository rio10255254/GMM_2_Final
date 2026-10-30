# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | v17probe | 0.611 | -6.826 | 3 | -11.058 | -100.446 |
| 2 | v17e3 | 4.429 | -11.116 | 3 | -39.981 | -125.552 |
| 3 | v19smoke | 4.566 | -8.842 | 3 | -40.921 | -126.355 |
| 4 | r61 | -796.142 | -73.673 | 4 | -124.846 | -1040.987 |
| 5 | v7 | -801.780 | -72.986 | 4 | -124.958 | -1046.737 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | v17e3 |
| 20260702_100MG | x_1um | primary | v19smoke |
| 20260704_20x_5x | 20x_0p5um | guardrail | v19smoke |
| 20260704_20x_5x | 20x_1um | guardrail | raw |
| 20260704_20x_5x | 5x_0p5um | guardrail | raw |
| 20260704_20x_5x | 5x_1um | guardrail | raw |
