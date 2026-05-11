# R40 External GMF Compare - `r39r40_avg_a025`

方法:原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step。

| scale | candidate step_std | COMBO step_std | delta % | status |
|---|---:|---:|---:|:---:|
| 8px | 0.146505 | 0.154515 | -5.18% | **IMPROVED** |
| 0p8px | 0.133546 | 0.131560 | +1.51% | **TRADEOFF_OK** |
| 0p08px | 0.100400 | 0.099891 | +0.51% | **TRADEOFF_OK** |

整體 verdict:**PASS_UPGRADE_GUARD**

R40 是 capacity 輪。`RESEARCH_CAPACITY_ONLY` 結果仍有研究價值,但不是升級候選。
