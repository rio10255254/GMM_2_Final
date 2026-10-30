# GMF-like thesis displacement gate

This gate uses fixed ROIs and the open GMF-like local fitting tool.
It is intended for model selection on thesis displacement behavior, not for training loss by itself.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.009449 | 1.004794 | ok |
| 20260702_100MG | x_1um | r61 | 0.009463 | 1.004324 | ok |
| 20260702_100MG | x_1um | v7 | 0.009017 | 1.004204 | ok |
| 20260702_100MG | x_1um | v11latest | 0.009385 | 1.004316 | ok |
| 20260702_100MG | x_0p5um | raw | 0.052380 | 0.511179 | ok |
| 20260702_100MG | x_0p5um | r61 | 0.051942 | 0.511642 | ok |
| 20260702_100MG | x_0p5um | v7 | 0.052086 | 0.511576 | ok |
| 20260702_100MG | x_0p5um | v11latest | 0.052226 | 0.511620 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.025650 | 1.001105 | ok |
| 20260704_20x_5x | 20x_1um | r61 | 0.028294 | 0.995996 | ok |
| 20260704_20x_5x | 20x_1um | v7 | 0.028575 | 0.997064 | ok |
| 20260704_20x_5x | 20x_1um | v11latest | 0.028659 | 1.000275 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.077762 | 0.491969 | ok |
| 20260704_20x_5x | 20x_0p5um | r61 | 0.077461 | 0.494856 | ok |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.077134 | 0.493749 | ok |
| 20260704_20x_5x | 20x_0p5um | v11latest | 0.077738 | 0.492305 | ok |
| 20260704_20x_5x | 5x_1um | raw | 0.162830 | 0.890681 | ok |
| 20260704_20x_5x | 5x_1um | r61 | 0.171846 | 0.893594 | ok |
| 20260704_20x_5x | 5x_1um | v7 | 0.170495 | 0.894100 | ok |
| 20260704_20x_5x | 5x_1um | v11latest | 0.166962 | 0.886643 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.021653 | 0.498002 | ok |
| 20260704_20x_5x | 5x_0p5um | r61 | 0.045308 | 0.517463 | ok |
| 20260704_20x_5x | 5x_0p5um | v7 | 0.042002 | 0.516139 | ok |
| 20260704_20x_5x | 5x_0p5um | v11latest | 0.024358 | 0.527683 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | r61 | 0.29% |
| 20260702_100MG | x_1um | v7 | 0.67% |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.03% |
| 20260704_20x_5x | 20x_1um | raw | -11.73% |
| 20260704_20x_5x | 5x_0p5um | raw | -12.50% |
| 20260704_20x_5x | 5x_1um | raw | -2.54% |
