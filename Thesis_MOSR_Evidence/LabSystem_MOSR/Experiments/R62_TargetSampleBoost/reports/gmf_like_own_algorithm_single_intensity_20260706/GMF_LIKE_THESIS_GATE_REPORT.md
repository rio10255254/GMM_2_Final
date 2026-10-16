# GMF-like thesis displacement gate

This gate uses fixed ROIs and the open GMF-like local fitting tool.
It is intended for model selection on thesis displacement behavior, not for training loss by itself.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.511835 | 0.003980 | ok |
| 20260702_100MG | x_1um | r61 | 0.508167 | 0.002836 | ok |
| 20260702_100MG | x_1um | v7 | 0.508437 | 0.002858 | ok |
| 20260702_100MG | x_0p5um | raw | 0.280120 | 0.010114 | ok |
| 20260702_100MG | x_0p5um | r61 | 0.281924 | 0.009978 | ok |
| 20260702_100MG | x_0p5um | v7 | 0.282143 | 0.009991 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.909110 | 0.018749 | ok |
| 20260704_20x_5x | 20x_1um | r61 | 0.864517 | 0.016943 | ok |
| 20260704_20x_5x | 20x_1um | v7 | 0.862087 | 0.016968 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.474535 | 0.014889 | ok |
| 20260704_20x_5x | 20x_0p5um | r61 | 0.445642 | 0.013987 | ok |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.444677 | 0.014030 | ok |
| 20260704_20x_5x | 5x_1um | raw | 1.155041 | 0.114528 | ok |
| 20260704_20x_5x | 5x_1um | r61 | 1.161332 | 0.106532 | ok |
| 20260704_20x_5x | 5x_1um | v7 | 1.158073 | 0.106505 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.634301 | 0.119989 | ok |
| 20260704_20x_5x | 5x_0p5um | r61 | 0.643246 | 0.114688 | ok |
| 20260704_20x_5x | 5x_0p5um | v7 | 0.643366 | 0.113588 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | raw | -0.72% |
| 20260702_100MG | x_1um | r61 | 0.66% |
| 20260704_20x_5x | 20x_0p5um | v7 | 6.29% |
| 20260704_20x_5x | 20x_1um | v7 | 5.17% |
| 20260704_20x_5x | 5x_0p5um | raw | -1.43% |
| 20260704_20x_5x | 5x_1um | raw | -0.26% |
