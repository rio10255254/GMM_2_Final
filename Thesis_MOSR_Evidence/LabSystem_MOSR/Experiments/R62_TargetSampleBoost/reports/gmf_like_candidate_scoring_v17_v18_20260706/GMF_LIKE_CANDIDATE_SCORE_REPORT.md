# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | v17probe | 0.611 | -6.826 | 3 | -11.058 | -100.446 |
| 2 | v7detail | 0.901 | -10.226 | 3 | -19.434 | -108.532 |
| 3 | v17e3 | 4.429 | -11.116 | 3 | -39.981 | -125.552 |
| 4 | v18e3 | -761.228 | 0.757 | 2 | -8.575 | -829.803 |
| 5 | r61 | -796.142 | -73.673 | 4 | -124.846 | -1040.987 |
| 6 | v7 | -801.780 | -72.986 | 4 | -124.958 | -1046.737 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | v17e3 |
| 20260702_100MG | x_1um | primary | v17e3 |
| 20260704_20x_5x | 20x_0p5um | guardrail | v17e3 |
| 20260704_20x_5x | 20x_1um | guardrail | raw |
| 20260704_20x_5x | 5x_0p5um | guardrail | v18e3 |
| 20260704_20x_5x | 5x_1um | guardrail | raw |
