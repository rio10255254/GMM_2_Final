# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | primary worse | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | blend10 | 0.023 | 0 | 2.080 | 0 | 0.000 | 2.426 | -2.402 |
| 2 | v24builtin | 0.061 | 0 | 1.562 | 2 | -0.168 | 2.424 | -62.531 |
| 3 | v25e3 | -0.026 | 1 | 1.467 | 0 | 0.000 | 2.428 | -102.538 |
| 4 | v25e1 | -0.018 | 1 | 2.114 | 1 | -0.159 | 2.427 | -132.695 |
| 5 | mix050 | -0.025 | 1 | 1.670 | 1 | -0.154 | 2.423 | -132.696 |
| 6 | mix025 | 0.010 | 1 | 1.855 | 1 | -0.281 | 2.422 | -132.718 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | blend10 |
| 20260702_100MG | x_1um | primary | v24builtin |
| 20260704_20x_5x | 20x_0p5um | guardrail | mix050 |
| 20260704_20x_5x | 20x_1um | guardrail | mix025 |
| 20260704_20x_5x | 5x_0p5um | guardrail | v25e1 |
| 20260704_20x_5x | 5x_1um | guardrail | v25e3 |
