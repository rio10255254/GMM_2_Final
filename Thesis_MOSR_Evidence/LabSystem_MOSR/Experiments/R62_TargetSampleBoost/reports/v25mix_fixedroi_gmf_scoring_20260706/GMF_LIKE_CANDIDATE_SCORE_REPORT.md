# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | blend10 | 0.023 | 18.071 | 0 | 0.000 | 2.287 | -2.263 |
| 2 | mix025 | 0.010 | 18.094 | 0 | 0.000 | 2.289 | -2.279 |
| 3 | v25e1 | -0.018 | 16.741 | 0 | 0.000 | 2.285 | -2.302 |
| 4 | mix050 | -0.025 | 16.753 | 0 | 0.000 | 2.287 | -2.312 |
| 5 | v25e3 | -0.026 | 10.514 | 0 | 0.000 | 2.304 | -2.330 |
| 6 | v24builtin | 0.061 | 17.769 | 1 | -0.020 | 2.292 | -32.250 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | blend10 |
| 20260702_100MG | x_1um | primary | v24builtin |
| 20260704_20x_5x | 20x_0p5um | guardrail | mix050 |
| 20260704_20x_5x | 20x_1um | guardrail | mix025 |
| 20260704_20x_5x | 5x_0p5um | guardrail | blend10 |
| 20260704_20x_5x | 5x_1um | guardrail | v25e3 |
