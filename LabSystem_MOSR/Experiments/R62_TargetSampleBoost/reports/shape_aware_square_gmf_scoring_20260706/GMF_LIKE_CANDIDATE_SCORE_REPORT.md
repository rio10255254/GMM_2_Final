# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | v17e3 | -0.102 | 1.827 | 1 | -0.022 | 2.424 | -32.547 |
| 2 | v22latest | -0.108 | 0.762 | 1 | -0.018 | 2.424 | -32.549 |
| 3 | v20e1m200 | -0.180 | 1.280 | 1 | -0.037 | 2.412 | -32.629 |
| 4 | r61 | 0.209 | -70.252 | 3 | -264.483 | 3.918 | -358.192 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | r61 |
| 20260702_100MG | x_1um | primary | r61 |
| 20260704_20x_5x | 20x_0p5um | guardrail | raw |
| 20260704_20x_5x | 20x_1um | guardrail | v17e3 |
| 20260704_20x_5x | 5x_0p5um | guardrail | v17e3 |
| 20260704_20x_5x | 5x_1um | guardrail | v22latest |
