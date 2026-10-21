# GMF-like thesis displacement gate

This gate uses fixed ROIs and the open GMF-like local fitting tool.
It is intended for model selection on thesis displacement behavior, not for training loss by itself.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.024995 | 0.999814 | ok |
| 20260702_100MG | x_1um | r61 | 0.422301 | 0.903308 | ok |
| 20260702_100MG | x_1um | v7 | 0.423655 | 0.903724 | ok |
| 20260702_100MG | x_1um | v8smoke | 0.422298 | 0.903308 | ok |
| 20260702_100MG | x_1um | v8probe120 | 0.423042 | 0.903469 | ok |
| 20260702_100MG | x_0p5um | raw | 0.042373 | 0.511274 | ok |
| 20260702_100MG | x_0p5um | r61 | 0.043543 | 0.509620 | ok |
| 20260702_100MG | x_0p5um | v7 | 0.046027 | 0.508243 | ok |
| 20260702_100MG | x_0p5um | v8smoke | 0.043541 | 0.509611 | ok |
| 20260702_100MG | x_0p5um | v8probe120 | 0.046045 | 0.508650 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.035031 | 1.003353 | ok |
| 20260704_20x_5x | 20x_1um | r61 | 0.045421 | 0.998299 | ok |
| 20260704_20x_5x | 20x_1um | v7 | 0.046646 | 0.998083 | ok |
| 20260704_20x_5x | 20x_1um | v8smoke | 0.045423 | 0.998289 | ok |
| 20260704_20x_5x | 20x_1um | v8probe120 | 0.046513 | 0.997968 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.080497 | 0.491105 | ok |
| 20260704_20x_5x | 20x_0p5um | r61 | 0.175064 | 0.494751 | ok |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.170723 | 0.496367 | ok |
| 20260704_20x_5x | 20x_0p5um | v8smoke | 0.175050 | 0.494750 | ok |
| 20260704_20x_5x | 20x_0p5um | v8probe120 | 0.168539 | 0.495671 | ok |
| 20260704_20x_5x | 5x_1um | raw | 0.322779 | 0.795890 | ok |
| 20260704_20x_5x | 5x_1um | r61 | 0.396083 | 0.456660 | ok |
| 20260704_20x_5x | 5x_1um | v7 | 0.392967 | 0.455888 | ok |
| 20260704_20x_5x | 5x_1um | v8smoke | 0.395919 | 0.456623 | ok |
| 20260704_20x_5x | 5x_1um | v8probe120 | 0.393897 | 0.450442 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.047274 | 0.551840 | ok |
| 20260704_20x_5x | 5x_0p5um | r61 | 0.106294 | 0.519209 | ok |
| 20260704_20x_5x | 5x_0p5um | v7 | 0.106347 | 0.517715 | ok |
| 20260704_20x_5x | 5x_0p5um | v8smoke | 0.106120 | 0.519620 | ok |
| 20260704_20x_5x | 5x_0p5um | v8probe120 | 0.112017 | 0.525432 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | raw | -8.66% |
| 20260702_100MG | x_1um | raw | -1592.49% |
| 20260704_20x_5x | 20x_0p5um | raw | -109.37% |
| 20260704_20x_5x | 20x_1um | raw | -32.78% |
| 20260704_20x_5x | 5x_0p5um | raw | -136.95% |
| 20260704_20x_5x | 5x_1um | raw | -22.03% |
