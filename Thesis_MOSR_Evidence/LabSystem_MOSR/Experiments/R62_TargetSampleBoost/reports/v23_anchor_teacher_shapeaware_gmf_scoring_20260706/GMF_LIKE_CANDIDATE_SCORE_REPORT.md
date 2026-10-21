# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | blend10 | 0.023 | 2.080 | 0 | 0.000 | 2.426 | -2.402 |
| 2 | v20 | -0.180 | 1.280 | 1 | -0.037 | 2.412 | -32.629 |
| 3 | v23best | 1.140 | -38.835 | 2 | -159.252 | 3.011 | -221.123 |
| 4 | v23latest | 0.721 | -59.228 | 2 | -239.677 | 3.134 | -302.090 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | v23best |
| 20260702_100MG | x_1um | primary | v23best |
| 20260704_20x_5x | 20x_0p5um | guardrail | blend10 |
| 20260704_20x_5x | 20x_1um | guardrail | v23latest |
| 20260704_20x_5x | 5x_0p5um | guardrail | blend10 |
| 20260704_20x_5x | 5x_1um | guardrail | v23best |
