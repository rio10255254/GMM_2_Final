# External GMF Five-Way Comparison: R18 vs R22h vs R25sw010 vs R26sm035 vs R27sm028

## Step Std（主要指標）
| 尺度 | round18_baseline | round22_hold | r25_sw010 | r26_sm035 | r27_sm028 | vs R26 | vs R18 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.250719 | 0.288654 | 0.211458 | 0.201031 | 0.197979 | -0.003052 | -0.052740 |
| 0.8px (pitch0p1um) | 0.285470 | 0.285453 | 0.211973 | 0.191336 | 0.196257 | +0.004921 | -0.089213 |
| 0.08px (pitch0p01um) | 0.209373 | 0.189303 | 0.164764 | 0.180313 | 0.172403 | -0.007910 | -0.036970 |

## Lag-1 Autocorrelation（anchor 穩定性）
| 尺度 | round18_baseline | round22_hold | r25_sw010 | r26_sm035 | r27_sm028 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.057390 | -0.084264 | 0.106957 | 0.083233 | 0.103608 |
| 0.8px (pitch0p1um) | 0.151332 | 0.202334 | 0.021065 | 0.225886 | 0.352671 |
| 0.08px (pitch0p01um) | 0.190600 | -0.097341 | -0.100989 | -0.010205 | -0.124960 |

## 結論
- 主戰場（0.8px）r27_sm028 step std = 0.196257
- r26_sm035 step std = 0.191336
- R27 是否優於 R26？ 否
- anchor lag-1 autocorr（R27）= 0.352671
- 建議：維持 R26 sm035

## Outlier Summary（0.8px）
| 模型 | 移除 step 數 | 原始 step std | 過濾後 step std |
| --- | ---: | ---: | ---: |
| round18_baseline | 0 | 0.285470 | 0.285470 |
| round22_hold | 0 | 0.285453 | 0.285453 |
| r25_sw010 | 0 | 0.211973 | 0.211973 |
| r26_sm035 | 0 | 0.191336 | 0.191336 |
| r27_sm028 | 0 | 0.196257 | 0.196257 |

## 方法註記
- `PosY` 直接由 `GMF_score.txt` 解析。
- `0.8px` 的 outlier 規則為 `|step - mean(step)| > 3 * std(step)`。
- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 anchor residual 計算。
- R18/R22h/R25 使用舊 pitch 目錄命名（`pitch0p1um_y_60` 等）；R26/R27 使用新命名（`pitch0p8px` 等）。