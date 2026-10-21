# GMF-like thesis displacement gate

This gate uses fixed ROIs and the open GMF-like local fitting tool.
It is intended for model selection on thesis displacement behavior, not for training loss by itself.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.611841 | 0.243238 | ok |
| 20260702_100MG | x_1um | r61 | 0.369574 | 0.908464 | ok |
| 20260702_100MG | x_1um | v7 | 0.662417 | 0.697978 | ok |
| 20260702_100MG | x_1um | v11latest | 0.376375 | 0.909089 | ok |
| 20260702_100MG | x_0p5um | raw | 0.053462 | 0.493593 | ok |
| 20260702_100MG | x_0p5um | r61 | 0.049877 | 0.490881 | ok |
| 20260702_100MG | x_0p5um | v7 | 0.049488 | 0.490575 | ok |
| 20260702_100MG | x_0p5um | v11latest | 0.051574 | 0.492953 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.404026 | 0.121283 | ok |
| 20260704_20x_5x | 20x_1um | r61 | 0.395556 | 0.175048 | ok |
| 20260704_20x_5x | 20x_1um | v7 | 0.378722 | 0.178772 | ok |
| 20260704_20x_5x | 20x_1um | v11latest | 0.413961 | 0.158332 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.098036 | 0.472959 | ok |
| 20260704_20x_5x | 20x_0p5um | r61 | 0.090987 | 0.472316 | ok |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.091526 | 0.472017 | ok |
| 20260704_20x_5x | 20x_0p5um | v11latest | 0.091509 | 0.471784 | ok |
| 20260704_20x_5x | 5x_1um | raw | 0.390053 | 0.226185 | ok |
| 20260704_20x_5x | 5x_1um | r61 | 0.185802 | 0.007472 | ok |
| 20260704_20x_5x | 5x_1um | v7 | 0.201105 | 0.003023 | ok |
| 20260704_20x_5x | 5x_1um | v11latest | 0.245275 | 0.015022 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.274335 | 0.422857 | ok |
| 20260704_20x_5x | 5x_0p5um | r61 | 0.145340 | 0.029087 | ok |
| 20260704_20x_5x | 5x_0p5um | v7 | 0.142494 | 0.019989 | ok |
| 20260704_20x_5x | 5x_0p5um | v11latest | 0.117241 | 0.030888 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | v7 | 7.43% |
| 20260702_100MG | x_1um | r61 | -8.27% |
| 20260704_20x_5x | 20x_0p5um | r61 | 6.64% |
| 20260704_20x_5x | 20x_1um | v7 | 6.26% |
| 20260704_20x_5x | 5x_0p5um | v11latest | 48.06% |
| 20260704_20x_5x | 5x_1um | r61 | 48.44% |
