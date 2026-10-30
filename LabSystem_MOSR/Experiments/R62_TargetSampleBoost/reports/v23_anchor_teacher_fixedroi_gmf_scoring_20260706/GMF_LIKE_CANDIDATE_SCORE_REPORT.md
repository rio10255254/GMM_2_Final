# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | blend10 | 0.023 | 18.071 | 0 | 0.000 | 2.287 | -2.263 |
| 2 | v23best | 1.140 | -2.575 | 2 | -12.055 | 2.728 | -73.643 |
| 3 | v23latest | 0.721 | -2.735 | 2 | -18.536 | 2.487 | -80.303 |
| 4 | v20 | -0.180 | -137.484 | 3 | -280.566 | 5.900 | -376.646 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | v23best |
| 20260702_100MG | x_1um | primary | v23best |
| 20260704_20x_5x | 20x_0p5um | guardrail | blend10 |
| 20260704_20x_5x | 20x_1um | guardrail | v23latest |
| 20260704_20x_5x | 5x_0p5um | guardrail | blend10 |
| 20260704_20x_5x | 5x_1um | guardrail | blend10 |
