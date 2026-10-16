# GMF-like thesis displacement gate

This gate uses fixed ROIs and the open GMF-like local fitting tool.
It is intended for model selection on thesis displacement behavior, not for training loss by itself.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.289343 | 0.003251 | ok |
| 20260702_100MG | x_1um | r61 | 0.303607 | 0.004167 | ok |
| 20260702_100MG | x_1um | v7 | 0.304386 | 0.004156 | ok |
| 20260702_100MG | x_0p5um | raw | 0.191047 | 0.008249 | ok |
| 20260702_100MG | x_0p5um | r61 | 0.204574 | 0.008425 | ok |
| 20260702_100MG | x_0p5um | v7 | 0.205225 | 0.008422 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.444384 | 0.005260 | ok |
| 20260704_20x_5x | 20x_1um | r61 | 0.507708 | 0.004450 | ok |
| 20260704_20x_5x | 20x_1um | v7 | 0.505486 | 0.004375 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.231950 | 0.000456 | ok |
| 20260704_20x_5x | 20x_0p5um | r61 | 0.269058 | 0.003213 | ok |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.267943 | 0.003167 | ok |
| 20260704_20x_5x | 5x_1um | raw | 0.378263 | 0.009563 | ok |
| 20260704_20x_5x | 5x_1um | r61 | 0.787417 | 0.011044 | ok |
| 20260704_20x_5x | 5x_1um | v7 | 0.782925 | 0.010440 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.256647 | 0.016179 | ok |
| 20260704_20x_5x | 5x_0p5um | r61 | 0.512290 | 0.015292 | ok |
| 20260704_20x_5x | 5x_0p5um | v7 | 0.503669 | 0.016343 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | raw | -7.42% |
| 20260702_100MG | x_1um | raw | -5.20% |
| 20260704_20x_5x | 20x_0p5um | raw | -15.52% |
| 20260704_20x_5x | 20x_1um | raw | -13.75% |
| 20260704_20x_5x | 5x_0p5um | raw | -96.25% |
| 20260704_20x_5x | 5x_1um | raw | -106.98% |
