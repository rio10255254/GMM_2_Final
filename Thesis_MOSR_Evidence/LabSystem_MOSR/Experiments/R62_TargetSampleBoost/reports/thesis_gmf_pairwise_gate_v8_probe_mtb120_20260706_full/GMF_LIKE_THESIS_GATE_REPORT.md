# GMF-like thesis displacement gate

This gate uses fixed ROIs and the open GMF-like local fitting tool.
It is intended for model selection on thesis displacement behavior, not for training loss by itself.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.009536 | 1.005108 | ok |
| 20260702_100MG | x_1um | r61 | 0.009402 | 1.005200 | ok |
| 20260702_100MG | x_1um | v7 | 0.009362 | 1.005219 | ok |
| 20260702_100MG | x_1um | v8smoke | 0.009404 | 1.005197 | ok |
| 20260702_100MG | x_1um | v8probe120 | 0.009396 | 1.005234 | ok |
| 20260702_100MG | x_0p5um | raw | 0.052563 | 0.511195 | ok |
| 20260702_100MG | x_0p5um | r61 | 0.052388 | 0.511140 | ok |
| 20260702_100MG | x_0p5um | v7 | 0.052373 | 0.511192 | ok |
| 20260702_100MG | x_0p5um | v8smoke | 0.052387 | 0.511135 | ok |
| 20260702_100MG | x_0p5um | v8probe120 | 0.052366 | 0.511172 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.025065 | 1.001315 | ok |
| 20260704_20x_5x | 20x_1um | r61 | 0.025353 | 0.996479 | ok |
| 20260704_20x_5x | 20x_1um | v7 | 0.025344 | 0.996771 | ok |
| 20260704_20x_5x | 20x_1um | v8smoke | 0.025351 | 0.996480 | ok |
| 20260704_20x_5x | 20x_1um | v8probe120 | 0.025439 | 0.997125 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.076356 | 0.492259 | ok |
| 20260704_20x_5x | 20x_0p5um | r61 | 0.077545 | 0.495468 | ok |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.077201 | 0.495492 | ok |
| 20260704_20x_5x | 20x_0p5um | v8smoke | 0.077547 | 0.495480 | ok |
| 20260704_20x_5x | 20x_0p5um | v8probe120 | 0.077277 | 0.495621 | ok |
| 20260704_20x_5x | 5x_1um | raw | 0.160710 | 0.891275 | ok |
| 20260704_20x_5x | 5x_1um | r61 | 0.157254 | 0.912045 | ok |
| 20260704_20x_5x | 5x_1um | v7 | 0.158132 | 0.907304 | ok |
| 20260704_20x_5x | 5x_1um | v8smoke | 0.157216 | 0.912000 | ok |
| 20260704_20x_5x | 5x_1um | v8probe120 | 0.172859 | 0.912509 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.012163 | 0.502568 | ok |
| 20260704_20x_5x | 5x_0p5um | r61 | 0.026884 | 0.520270 | ok |
| 20260704_20x_5x | 5x_0p5um | v7 | 0.025546 | 0.519010 | ok |
| 20260704_20x_5x | 5x_0p5um | v8smoke | 0.026983 | 0.520040 | ok |
| 20260704_20x_5x | 5x_0p5um | v8probe120 | 0.024762 | 0.520904 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | v8probe120 | 0.38% |
| 20260702_100MG | x_1um | v7 | 1.47% |
| 20260704_20x_5x | 20x_0p5um | raw | -1.21% |
| 20260704_20x_5x | 20x_1um | raw | -1.49% |
| 20260704_20x_5x | 5x_0p5um | raw | -103.59% |
| 20260704_20x_5x | 5x_1um | v8smoke | -7.56% |
