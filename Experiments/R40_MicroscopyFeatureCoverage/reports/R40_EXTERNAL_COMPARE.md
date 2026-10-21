# R40 外部 GMF 比較 — `r40_combo_best_avg_a045`

方法:原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step。

| scale | candidate step_std | COMBO step_std | delta % | status |
|---|---:|---:|---:|:---:|
| 8px | 0.189750 | 0.154515 | +22.80% | **REGRESSED** |
| 0p8px | 0.133314 | 0.131560 | +1.33% | **TRADEOFF_OK** |
| 0p08px | 0.097048 | 0.099891 | -2.85% | **IMPROVED** |

整體 verdict:**RESEARCH_CAPACITY_ONLY**

逐 step audit:

| scale | frames | steps used | z>5 removed | median step | min step | max step | mean abs error vs nominal |
|---|---:|---:|---:|---:|---:|---:|---:|
| 8px | 100 | 99 | 0 | -8.020000 | -8.520000 | -7.630000 | 0.147283 |
| 0p8px | 60 | 59 | 0 | -0.811000 | -1.157000 | -0.511000 | 0.106356 |
| 0p08px | 40 | 39 | 0 | -0.068000 | -0.306000 | 0.103000 | 0.058744 |

逐 step 詳細 CSV:

- `results/external_gmf/step_audit/pitch8px_steps.csv`
- `results/external_gmf/step_audit/pitch0p8px_steps.csv`
- `results/external_gmf/step_audit/pitch0p08px_steps.csv`
- `results/external_gmf/step_audit/step_audit_summary.json`

R40 是 capacity 輪。外部結果確認 capacity 發現,但 `r40_combo_best_avg_a045` 不是升級候選——8px 外部 ring guard 比 COMBO 退步 +22.80%。
