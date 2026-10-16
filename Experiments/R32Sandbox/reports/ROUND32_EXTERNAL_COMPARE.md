# Round32 External GMF Compare: R30 B1 dironly vs R32 Sandbox Winner

Last updated: 2026-03-20

## Step Std（主要指標）
| 尺度 | r30_b1_dironly | r32_real_eq_finetune | delta |
| --- | ---: | ---: | ---: |
| 8px | 0.205193 | 0.319667 | 0.114475 |
| 0.8px | 0.167862 | 0.331821 | 0.163960 |
| 0.08px | 0.157720 | 0.230119 | 0.072399 |

## Lag-1 Autocorrelation（0.8px anchor 穩定性）
| model | `0.8px lag-1 autocorr` |
| --- | ---: |
| `r30_b1_dironly` | 0.267027 |
| `r32_real_eq_finetune` | 0.197257 |

## Outlier Summary（0.8px）
| model | 移除 step 數 | 原始 step std | 過濾後 step std |
| --- | ---: | ---: | ---: |
| `r30_b1_dironly` | 0 | 0.167862 | 0.167862 |
| `r32_real_eq_finetune` | 1 | 0.331821 | 0.303349 |

## Verdict
- baseline `r30_b1_dironly` main battlefield = 0.167862
- candidate `r32_real_eq_finetune` main battlefield = 0.331821 (+97.7% vs R30)
- 8px guard delta = 0.114475
- main battlefield win: NO
- macro guard ok: NO
- final upgrade verdict: FAIL

## 方法註記
- `PosY` 直接由 `GMF_score.txt` 解析。
- `step[i] = PosY[i+1] - PosY[i]`。
- `0.8px` outlier 規則為 `|step - mean(step)| > 3 * std(step)`。
- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 residual 計算。