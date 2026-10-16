# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | v7_anchor_blend10 | 0.023 | 18.071 | 0 | 0.000 | 2.287 | -2.263 |
| 2 | r61 | 0.209 | 15.379 | 1 | -0.336 | 2.905 | -33.033 |
| 3 | v7_anchor_detail035 | -0.087 | -7.611 | 1 | -37.826 | 2.623 | -70.536 |
| 4 | v17e3_detail010 | 0.027 | -16.438 | 3 | -63.206 | 2.874 | -156.052 |
| 5 | v20e1m200 | -0.180 | -137.484 | 3 | -280.566 | 5.900 | -376.646 |
| 6 | v17e3 | -0.102 | -152.250 | 3 | -344.806 | 6.334 | -441.242 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | r61 |
| 20260702_100MG | x_1um | primary | r61 |
| 20260704_20x_5x | 20x_0p5um | guardrail | v7_anchor_detail035 |
| 20260704_20x_5x | 20x_1um | guardrail | v7_anchor_detail035 |
| 20260704_20x_5x | 5x_0p5um | guardrail | v7_anchor_blend10 |
| 20260704_20x_5x | 5x_1um | guardrail | v7_anchor_blend10 |
