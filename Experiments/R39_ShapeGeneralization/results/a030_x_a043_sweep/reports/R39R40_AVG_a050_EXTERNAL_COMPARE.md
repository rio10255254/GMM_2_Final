# R40 External GMF Compare - `r39r40_avg_a050`

方法:原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step。

| scale | candidate step_std | COMBO step_std | delta % | status |
|---|---:|---:|---:|:---:|
| 8px | 0.151365 | 0.154515 | -2.04% | **IMPROVED** |
| 0p8px | 0.149209 | 0.131560 | +13.41% | **REGRESSED** |
| 0p08px | 0.093177 | 0.099891 | -6.72% | **IMPROVED** |

整體 verdict:**RESEARCH_CAPACITY_ONLY**

R40 是 capacity 輪。`RESEARCH_CAPACITY_ONLY` 結果仍有研究價值,但不是升級候選。
