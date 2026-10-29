# Round30 External GMF Compare: R26sm035 vs R30 B1 Candidates

Last updated: 2026-03-18

## Step Std（主要指標）
| 尺度 | r26_sm035 | r30_b1_dironly | r30_b1a1_dir_lblur | r30_b1a1a5_full |
| --- | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.201031 | 0.205193 | 0.204185 | 0.199290 |
| 0.8px (pitch0p1um) | 0.191336 | 0.167862 | 0.185450 | 0.184304 |
| 0.08px (pitch0p01um) | 0.180313 | 0.157720 | 0.141429 | 0.157356 |

## Delta vs R26（step std）
| candidate | `8px` vs R26 | `0.8px` vs R26 | `0.08px` vs R26 |
| --- | ---: | ---: | ---: |
| `r30_b1_dironly` | +0.004162 | -0.023475 | -0.022592 |
| `r30_b1a1_dir_lblur` | +0.003154 | -0.005886 | -0.038884 |
| `r30_b1a1a5_full` | -0.001741 | -0.007032 | -0.022957 |

## Lag-1 Autocorrelation（anchor 穩定性）
| 尺度 | r26_sm035 | r30_b1_dironly | r30_b1a1_dir_lblur | r30_b1a1a5_full |
| --- | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.083233 | 0.027121 | 0.125237 | 0.109862 |
| 0.8px (pitch0p1um) | 0.225886 | 0.267027 | 0.274848 | 0.164857 |
| 0.08px (pitch0p01um) | -0.010205 | -0.181258 | 0.204624 | -0.304034 |

## Outlier Summary（0.8px）
| 模型 | 移除 step 數 | 原始 step std | 過濾後 step std |
| --- | ---: | ---: | ---: |
| r26_sm035 | 0 | 0.191336 | 0.191336 |
| r30_b1_dironly | 0 | 0.167862 | 0.167862 |
| r30_b1a1_dir_lblur | 0 | 0.185450 | 0.185450 |
| r30_b1a1a5_full | 0 | 0.184304 | 0.184304 |

## Verdict
- 主戰場（`0.8px`）external winner 是 `r30_b1_dironly = 0.167862`，相對 `R26 = 0.191336` 改善 `-0.023475`
- `r30_b1a1_dir_lblur` 與 `r30_b1a1a5_full` 都優於 `R26`，但都沒有擊敗 `r30_b1_dironly`
- `r30_b1a1a5_full` 的 `8px` 最佳，但 production 決策仍以 `0.8px` 主戰場優先
- 結論：正式升級 `Round30 / r30_b1_dironly` 為新 production baseline；下一步進入 `Round31 B1 hyperparam tuning`

## 方法註記
- `PosY` 直接由 `Traing_Progress/organized_20260316/round30/gmf_results/raw*\pitch*\GMF_score.txt` 解析
- `step[i] = PosY[i+1] - PosY[i]`
- `0.8px` outlier 規則沿用既有 compare workflow：`|step - mean(step)| > 3 * std(step)`
- `lag-1 autocorr` 定義為每個模型自身 `PosY` 經線性去趨勢後的 anchor residual Pearson lag-1 correlation
