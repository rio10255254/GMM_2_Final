# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | blend10 | 0.023 | 2.080 | 0 | 0.000 | 2.426 | -2.402 |
| 2 | v24builtin | 0.061 | 1.562 | 2 | -0.168 | 2.424 | -62.531 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | blend10 |
| 20260702_100MG | x_1um | primary | v24builtin |
| 20260704_20x_5x | 20x_0p5um | guardrail | blend10 |
| 20260704_20x_5x | 20x_1um | guardrail | v24builtin |
| 20260704_20x_5x | 5x_0p5um | guardrail | blend10 |
| 20260704_20x_5x | 5x_1um | guardrail | blend10 |
