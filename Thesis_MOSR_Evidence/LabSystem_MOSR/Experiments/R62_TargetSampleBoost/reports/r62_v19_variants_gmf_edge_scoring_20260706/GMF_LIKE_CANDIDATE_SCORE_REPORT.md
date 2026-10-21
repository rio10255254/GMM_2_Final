# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | r61 | 23.151 | 27.168 | 0 | 0.000 | 23.151 |
| 2 | v19e1m120 | 14.018 | 25.435 | 0 | 0.000 | 14.018 |
| 3 | v19e1m300 | 8.218 | 26.875 | 0 | 0.000 | 8.218 |
| 4 | v7 | -0.416 | 27.351 | 0 | 0.000 | -0.416 |
| 5 | v17e3 | -2.548 | 24.665 | 0 | 0.000 | -2.548 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | v7 |
| 20260702_100MG | x_1um | primary | r61 |
| 20260704_20x_5x | 20x_0p5um | guardrail | r61 |
| 20260704_20x_5x | 20x_1um | guardrail | v19e1m300 |
| 20260704_20x_5x | 5x_0p5um | guardrail | v7 |
| 20260704_20x_5x | 5x_1um | guardrail | v19e1m300 |
