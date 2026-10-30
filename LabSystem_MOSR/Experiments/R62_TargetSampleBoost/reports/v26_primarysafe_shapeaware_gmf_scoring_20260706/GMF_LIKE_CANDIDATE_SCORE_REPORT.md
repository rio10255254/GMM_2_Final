# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | primary worse | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | blend10 | 0.023 | 0 | 2.080 | 0 | 0.000 | 2.426 | -2.402 |
| 2 | v24builtin | 0.061 | 0 | 1.562 | 2 | -0.168 | 2.424 | -62.531 |
| 3 | v25e1 | -0.018 | 1 | 2.114 | 1 | -0.159 | 2.427 | -132.695 |
| 4 | v26 | -0.003 | 1 | 1.596 | 1 | -0.244 | 2.424 | -132.719 |
| 5 | v20 | -0.180 | 1 | 1.280 | 1 | -0.037 | 2.412 | -133.005 |
| 6 | r61 | 0.209 | 0 | -70.252 | 3 | -264.483 | 3.918 | -358.192 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | r61 |
| 20260702_100MG | x_1um | primary | r61 |
| 20260704_20x_5x | 20x_0p5um | guardrail | v25e1 |
| 20260704_20x_5x | 20x_1um | guardrail | v25e1 |
| 20260704_20x_5x | 5x_0p5um | guardrail | v25e1 |
| 20260704_20x_5x | 5x_1um | guardrail | v20 |
