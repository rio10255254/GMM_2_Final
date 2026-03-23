# Round31 External GMF Compare: R30 B1 dironly vs R31 Candidates

Last updated: 2026-03-19

## Step Std（主要指標）
| 尺度 | r30_b1_dironly | r31_eq_prob_up | r31_eq_weight_up | r31_edge_ratio_low |
| --- | ---: | ---: | ---: | ---: |
| 8px | 0.205193 | 0.185461 | 0.192651 | 0.210608 |
| 0.8px | 0.167862 | 0.184867 | 0.185458 | 0.179347 |
| 0.08px | 0.157720 | 0.142645 | 0.154121 | 0.148324 |

## Delta vs R30（0.8px）
| candidate | `0.8px std` | delta vs R30 | pct vs R30 |
| --- | ---: | ---: | ---: |
| `r31_eq_prob_up` | 0.184867 | 0.017006 | +10.1% |
| `r31_eq_weight_up` | 0.185458 | 0.017596 | +10.5% |
| `r31_edge_ratio_low` | 0.179347 | 0.011486 | +6.8% |

## Lag-1 Autocorrelation（0.8px anchor 穩定性）
| model | `0.8px lag-1 autocorr` |
| --- | ---: |
| `r30_b1_dironly` | 0.267027 |
| `r31_eq_prob_up` | 0.155306 |
| `r31_eq_weight_up` | 0.373179 |
| `r31_edge_ratio_low` | 0.381414 |

## Outlier Summary（0.8px）
| model | 移除 step 數 | 原始 step std | 過濾後 step std |
| --- | ---: | ---: | ---: |
| `r30_b1_dironly` | 0 | 0.167862 | 0.167862 |
| `r31_eq_prob_up` | 0 | 0.184867 | 0.184867 |
| `r31_eq_weight_up` | 0 | 0.185458 | 0.185458 |
| `r31_edge_ratio_low` | 0 | 0.179347 | 0.179347 |

## Missing External Artifact
- `r31_eq_combo`：expected raw root `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\gmf_results\raw\r31_eq_combo` but no `GMF_score.txt` was found. It is treated as external artifact missing, not a measured regression.

## Verdict
- measured Round31 candidates all regressed on the `0.8px` main battlefield relative to `r30_b1_dironly = 0.167862`
- `r31_eq_prob_up`、`r31_eq_weight_up`、`r31_edge_ratio_low` 都不符合升級條件
- `r31_eq_combo` 缺少 external artifact，因此不列入 measured regression winner table
- 結論：維持 `Round30 / r30_b1_dironly` 為 production baseline

## 方法註記
- `PosY` 直接由 `GMF_score.txt` 解析。
- `step[i] = PosY[i+1] - PosY[i]`。
- `0.8px` outlier 規則為 `|step - mean(step)| > 3 * std(step)`。
- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 residual 計算。