# External GMF Three-Way Comparison: R18 vs R22h vs R25sw010

## Step Std（主要指標）
| 尺度 | round18_baseline | round22_hold | r25_sw010 | vs R18 | vs R22h |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.250719 | 0.288654 | 0.211458 | -0.039261 | -0.077196 |
| 0.8px (pitch0p1um) | 0.285470 | 0.285453 | 0.211973 | -0.073497 | -0.073481 |
| 0.08px (pitch0p01um) | 0.209373 | 0.189303 | 0.164764 | -0.044609 | -0.024538 |

## Lag-1 Autocorrelation（anchor 穩定性）
| 尺度 | round18_baseline | round22_hold | r25_sw010 |
| --- | ---: | ---: | ---: |
| 8px (pitch1um) | 0.057390 | -0.084264 | 0.106957 |
| 0.8px (pitch0p1um) | 0.151332 | 0.202334 | 0.021065 |
| 0.08px (pitch0p01um) | 0.190600 | -0.097341 | -0.100989 |

## 結論
- 主戰場（0.8px）r25_sw010 step std 0.211973 是否 < 0.2855（R18/R22h 水準）？ 是
- anchor lag-1 autocorr 0.021065 是否 ≥ 0.10？ 否
- 建議：維持 R22h

## 方法註記
- `PosY` 直接由 `GMF_score.txt` 解析。
- `pitch0p1um_y_60` 的 outlier 規則為 `|step - mean(step)| > 3 * std(step)`。
- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 anchor residual 計算，作為單模型版本的 anchor 穩定性指標。

## Outlier Summary（0.8px）
| 模型 | 移除 step 數 | 原始 step std | 過濾後 step std |
| --- | ---: | ---: | ---: |
| round18_baseline | 0 | 0.285470 | 0.285470 |
| round22_hold | 0 | 0.285453 | 0.285453 |
| r25_sw010 | 0 | 0.211973 | 0.211973 |
