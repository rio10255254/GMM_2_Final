# R40 External GMF Compare - `r40_combo_best_avg_a043`

方法:原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step。

| scale | candidate step_std | COMBO step_std | delta % | status |
|---|---:|---:|---:|:---:|
| 8px | 0.145379 | 0.154515 | -5.91% | **IMPROVED** |
| 0p8px | 0.127411 | 0.131560 | -3.15% | **IMPROVED** |
| 0p08px | 0.121382 | 0.099891 | +21.51% | **REGRESSED** |

整體 verdict:**RESEARCH_CAPACITY_ONLY**

R40 是 capacity 輪。`RESEARCH_CAPACITY_ONLY` 結果仍有研究價值,但不是升級候選。
