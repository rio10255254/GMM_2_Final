# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | v7_anchor_blend10 | 0.023 | 2.080 | 0 | 0.000 | 2.426 | -2.402 |
| 2 | v17e3_detail010 | 0.027 | 2.056 | 1 | -0.062 | 2.467 | -32.501 |
| 3 | v17e3 | -0.102 | 1.827 | 1 | -0.022 | 2.424 | -32.547 |
| 4 | v7_anchor_detail035 | -0.087 | 2.093 | 1 | -0.109 | 2.409 | -32.605 |
| 5 | v20e1m200 | -0.180 | 1.280 | 1 | -0.037 | 2.412 | -32.629 |
| 6 | v17e3_detail035 | -0.041 | 0.005 | 2 | -0.411 | 2.481 | -62.933 |
| 7 | v17e3_detail020 | 0.025 | 0.497 | 2 | -0.560 | 2.469 | -63.004 |
| 8 | r61 | 0.209 | -70.252 | 3 | -264.483 | 3.918 | -358.192 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | r61 |
| 20260702_100MG | x_1um | primary | r61 |
| 20260704_20x_5x | 20x_0p5um | guardrail | v7_anchor_detail035 |
| 20260704_20x_5x | 20x_1um | guardrail | v7_anchor_detail035 |
| 20260704_20x_5x | 5x_0p5um | guardrail | v17e3_detail010 |
| 20260704_20x_5x | 5x_1um | guardrail | v20e1m200 |
