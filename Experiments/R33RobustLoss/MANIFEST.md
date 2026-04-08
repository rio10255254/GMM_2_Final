# R33 — Robust Loss (Winsorize Spatial Loss)

| 欄位 | 值 |
|------|---|
| Round | 33 |
| Branch | `sandbox/r33` |
| Status | **External PASS** — GMF 極致型候選 |
| Mechanism | Winsorize gradient_magnitude_loss + laplacian_hf_loss at 95th percentile |
| External GMF 0.8px | **0.119049** (-29.1% vs R30) |
| Checkpoint | `Traing_Progress/..._20260405_091941/weights/best_tradeoff.pth.tar` |
| Key Reports | `reports/R33_EXPERIMENT_SUMMARY.md`, `reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md` |

## Scope: Series Hub

此目錄不只是 R33 的實驗記錄——它也是 R33-R38v2 整個系列的**文件中心**：
- R33 ablation 報告（lap_only、soft_p95、p90）
- `R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`：12 候選完整系列報告
- `GMF_STEP_STD_METHODOLOGY.md`：跨實驗的 GMF 計算方法論
- `QUANTIZATION_FIX_ANALYSIS.md`：跨實驗的量化修復影響分析
- `INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md`：跨實驗的 Internal/External 偏差分析

這些跨實驗文件放在此處是因為 R33 是系列的起點——所有後續實驗（R34-R38v2/COMBO）
的基礎設施（Winsorize、_robust_clip 等）都源自此目錄的程式碼改動。
