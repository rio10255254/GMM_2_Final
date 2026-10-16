# V41.1 quick fine-tune local edge validation

This package compares Raw, V41-Standalone, and V41.1 quick fine-tune using the same local-edge displacement method.

## Main common-best-30 result

| 資料集          |   Raw SD(nm) |   正式V41 SD(nm) |   V41.1 SD(nm) |   V41.1相對Raw改善(%) |   V41.1相對正式V41改善(%) |   Raw邊界不確定度(nm) |   V41.1邊界不確定度(nm) |   邊界不確定度改善(%) |
|:----------------|-------------:|-----------------:|---------------:|----------------------:|--------------------------:|----------------------:|------------------------:|----------------------:|
| 50x 0.5 um/step |        28.79 |            25.3  |          25.07 |                 12.9  |                      0.88 |                218.79 |                  103.89 |                 52.51 |
| 50x 1 um/step   |        31.28 |            31.8  |          31.83 |                 -1.76 |                     -0.09 |                477.03 |                  257.36 |                 46.05 |
| 20x 0.5 um/step |        20.14 |            27.4  |          27.54 |                -36.72 |                     -0.49 |                202.78 |                  101.01 |                 50.19 |
| 20x 1 um/step   |        50.42 |            34.01 |          34.21 |                 32.14 |                     -0.59 |                176.8  |                   87.06 |                 50.76 |
| 5x 0.5 um/step  |         8.91 |             9.55 |           9.59 |                 -7.62 |                     -0.4  |                473.47 |                  355.88 |                 24.83 |
| 5x 1 um/step    |        61.93 |            60.93 |          60.97 |                  1.54 |                     -0.07 |                487.35 |                  365.51 |                 25    |

## Outputs

- tables/v41_1_local_edge_delta.csv
- tables/v41_1_local_edge_summary_by_case.csv
- tables/v41_1_local_edge_step_measurements.csv
- figures/*_std_compare.png