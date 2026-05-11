# R40 External GMF Compare - `r39r40_avg_a075`

方法:原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step。

| scale | candidate step_std | COMBO step_std | delta % | status |
|---|---:|---:|---:|:---:|
| 8px | 0.144254 | 0.154515 | -6.64% | **IMPROVED** |
| 0p8px | 0.152095 | 0.131560 | +15.61% | **REGRESSED** |
| 0p08px | 0.111468 | 0.099891 | +11.59% | **REGRESSED** |

整體 verdict:**RESEARCH_CAPACITY_ONLY**

R40 是 capacity 輪。`RESEARCH_CAPACITY_ONLY` 結果仍有研究價值,但不是升級候選。
