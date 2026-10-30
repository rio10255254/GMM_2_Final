# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | v19e1m200 | 4.101 | -5.059 | 2 | -42.577 | 3.761 | -102.237 |
| 2 | v19e1m300 | 4.365 | -10.221 | 3 | -39.842 | 3.693 | -129.170 |
| 3 | v19e1m120 | 4.566 | -8.842 | 3 | -40.921 | 3.705 | -130.060 |
| 4 | v17e3 | 4.429 | -11.116 | 3 | -39.981 | 4.661 | -130.213 |
| 5 | r61 | -796.142 | -73.673 | 4 | -124.846 | 12.434 | -1053.422 |
| 6 | v7 | -801.780 | -72.986 | 4 | -124.958 | 12.318 | -1059.056 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | v19e1m300 |
| 20260702_100MG | x_1um | primary | v19e1m120 |
| 20260704_20x_5x | 20x_0p5um | guardrail | v19e1m300 |
| 20260704_20x_5x | 20x_1um | guardrail | raw |
| 20260704_20x_5x | 5x_0p5um | guardrail | v19e1m200 |
| 20260704_20x_5x | 5x_1um | guardrail | raw |
