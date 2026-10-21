# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | r61 | 0.209 | 15.379 | 1 | -0.336 | 2.905 | -33.033 |
| 2 | v20e1m200 | -0.180 | -137.484 | 3 | -280.566 | 5.900 | -376.646 |
| 3 | v17e3 | -0.102 | -152.250 | 3 | -344.806 | 6.334 | -441.242 |
| 4 | v22latest | -0.108 | -453.972 | 3 | -1518.080 | 8.839 | -1617.027 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | r61 |
| 20260702_100MG | x_1um | primary | r61 |
| 20260704_20x_5x | 20x_0p5um | guardrail | raw |
| 20260704_20x_5x | 20x_1um | guardrail | v17e3 |
| 20260704_20x_5x | 5x_0p5um | guardrail | r61 |
| 20260704_20x_5x | 5x_1um | guardrail | r61 |
