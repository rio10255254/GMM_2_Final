# GMF-like thesis displacement gate

This gate uses fixed ROIs and an open local feature fitting tracker.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.009391 | 1.005026 | ok |
| 20260702_100MG | x_1um | blend10 | 0.009392 | 1.005022 | ok |
| 20260702_100MG | x_1um | v24builtin | 0.009383 | 1.005022 | ok |
| 20260702_100MG | x_0p5um | raw | 0.052039 | 0.511158 | ok |
| 20260702_100MG | x_0p5um | blend10 | 0.052010 | 0.511169 | ok |
| 20260702_100MG | x_0p5um | v24builtin | 0.052017 | 0.511165 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.025569 | 1.000833 | ok |
| 20260704_20x_5x | 20x_1um | blend10 | 0.025489 | 1.000366 | ok |
| 20260704_20x_5x | 20x_1um | v24builtin | 0.025461 | 1.000420 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.076249 | 0.491675 | ok |
| 20260704_20x_5x | 20x_0p5um | blend10 | 0.076219 | 0.491821 | ok |
| 20260704_20x_5x | 20x_0p5um | v24builtin | 0.076264 | 0.491816 | ok |
| 20260704_20x_5x | 5x_1um | raw | 0.185078 | 0.871645 | ok |
| 20260704_20x_5x | 5x_1um | blend10 | 0.159571 | 0.891018 | ok |
| 20260704_20x_5x | 5x_1um | v24builtin | 0.159491 | 0.890304 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.041139 | 0.489850 | ok |
| 20260704_20x_5x | 5x_0p5um | blend10 | 0.017217 | 0.499363 | ok |
| 20260704_20x_5x | 5x_0p5um | v24builtin | 0.017752 | 0.500305 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | blend10 | 0.04% |
| 20260702_100MG | x_1um | v24builtin | 0.08% |
| 20260704_20x_5x | 20x_0p5um | blend10 | -0.02% |
| 20260704_20x_5x | 20x_1um | v24builtin | 0.42% |
| 20260704_20x_5x | 5x_0p5um | blend10 | 56.85% |
| 20260704_20x_5x | 5x_1um | v24builtin | 13.82% |
