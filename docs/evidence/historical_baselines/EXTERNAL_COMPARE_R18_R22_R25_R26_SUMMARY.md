# External GMF Four-Way Comparison: R18 vs R22h vs R25sw010 vs R26sm035

## Step Std（主要指標）
| 尺度 | round18_baseline | round22_hold | r25_sw010 | r26_sm035 | vs R25 | vs R18 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.250719 | 0.288654 | 0.211458 | 0.201031 | -0.010428 | -0.049689 |
| 0.8px (pitch0p1um) | 0.285470 | 0.285453 | 0.211973 | 0.191336 | -0.020637 | -0.094134 |
| 0.08px (pitch0p01um) | 0.209373 | 0.189303 | 0.164764 | 0.180313 | +0.015548 | -0.029061 |

## Lag-1 Autocorrelation（anchor 穩定性）
| 尺度 | round18_baseline | round22_hold | r25_sw010 | r26_sm035 |
| --- | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.057390 | -0.084264 | 0.106957 | 0.083233 |
| 0.8px (pitch0p1um) | 0.151332 | 0.202334 | 0.021065 | 0.225886 |
| 0.08px (pitch0p01um) | 0.190600 | -0.097341 | -0.100989 | -0.010205 |

## 結論
- 主戰場（0.8px）r26_sm035 step std = 0.191336
- r25_sw010 step std = 0.211973
- R26 是否優於 R25？ 是
- anchor lag-1 autocorr（R26）= 0.225886
- 建議：升級 R26 sm035 為新 baseline

## Outlier Summary（0.8px）
| 模型 | 移除 step 數 | 原始 step std | 過濾後 step std |
| --- | ---: | ---: | ---: |
| round18_baseline | 0 | 0.285470 | 0.285470 |
| round22_hold | 0 | 0.285453 | 0.285453 |
| r25_sw010 | 0 | 0.211973 | 0.211973 |
| r26_sm035 | 0 | 0.191336 | 0.191336 |
