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

**此目錄也包含**：R33 的所有 ablation（lap_only、soft_p95、p90）、
量化修復分析、GMF 方法論、Internal/External 偏差分析、完整系列報告。
是整個 R33-R38v2 系列的文件中心。
