# R42 Manifest

## 實驗身份

- Round：R42
- 名稱：顯微邊界忠實度
- 目錄：`Experiments/R42_MicroscopyBoundaryFidelity/`
- 分支：`sandbox/r42`
- 主要目標：建立通用顯微結構邊界忠實重建能力。

## 主要檔案

| 類型 | 位置 | 用途 |
|------|------|------|
| 資料產生 | `scripts/r42_boundary_data.py` | 產生 R42 合成邊界資料、幾何標註與訓練包 |
| 邊界評估 | `scripts/r42_boundary_metrics.py` | 計算邊界距離、F-score、中心線與格線誤差 |
| 訓練啟動 | `scripts/launch_r42.py` | 啟動 R42 兩個候選 |
| 重建驗證 | `scripts/run_r42_boundary_recon.py` | 跑 R42 邊界驗證重建 |
| 環形守門 | `scripts/run_r42_ring_guard.py` | 跑本地三尺度環形分析 |
| 權重平均 | `scripts/r42_weight_sweep.py` | 建立 COMBO ↔ R42 低比例平均權重 |
| 權重平均評估 | `scripts/run_r42_weight_sweep.py` | 評估低比例平均權重的邊界能力與本地環形守門 |
| 外部比較 | `scripts/r42_external_compare.py` | 彙整外部 GMF 結果 |
| 測試 | `tests/` | R42 資料、指標、訓練器幾何接線測試 |
| 報告 | `reports/R42_RESULTS.md` | R42 canonical 結果紀錄 |
| 外部報告 | `reports/R42_EXTERNAL_COMPARE.md` | R42 三個候選的外部 GMF 補測彙整 |

## 目前狀態

- 設施已建立。
- 正式訓練已完成：`r42_boundary_from_combo` 與 `r42_boundary_from_r41` 各 50 epoch。
- 顯微邊界驗證已完成：COMBO、R39 a030、R40 a045、R41 direct、R42 四個權重共 8 組。
- 本地三尺度環形守門已完成：R42 四個權重皆未守住 COMBO。
- 低比例權重平均補測已完成：0.01、0.02、0.03、0.05 四點皆未形成共同通過點。
- 守門 KD 短訓練診斷已完成：邊界能力仍強，但本地三尺度環形守門更差，判定靜態老師牽引不足。
- 外部 GMF 補測已完成：`r42_r41_best`、`r42_combo_latest`、`r42_r41_latest` 三個候選皆退步過大，R42 仍為 research-only，不建議作量測替代。

## 主要產物

| 類型 | 位置 | 說明 |
|------|------|------|
| R42 訓練輸出 | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r42_boundary_from_combo_20260505_142301/` | D 保留代表模型；完整 run 依 `ARCHIVE_POINTER_20260824.md` 從 H 恢復 |
| R42 訓練輸出 | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r42_boundary_from_r41_20260505_145229/` | D 保留代表模型；完整 run 依 `ARCHIVE_POINTER_20260824.md` 從 H 恢復 |
| 邊界重建結果 | `results/boundary_recon/` | 8 組顯微邊界重建與摘要 |
| 代表圖 | `results/boundary_recon/r42_representative_boundary_sheet.png` | Grid / Curve / Defect / Mixed 代表圖 |
| 指標除錯圖 | `results/boundary_recon/r42_curve_metric_debug_0080.png` | 曲線指標修正用檢查圖 |
| 環形重建結果 | `results/ring_recon/` | R42 四個權重的三尺度環形重建 |
| 環形守門摘要 | `results/ring_guard/*_ring_guard_summary.json` | R42 四個權重的本地環形守門結果 |
| 低 alpha 權重平均 | `results/weight_sweep/r42_r41_best_lowalpha/` | COMBO ↔ `r42_r41_best` 低比例平均、邊界驗證與本地環形守門 |
| 守門 KD 診斷訓練 | `results/archive_retained_20260824/training_checkpoints/training_progress_GESR_v1_v5_ST0p8_SWP_r42_boundary_guarded_kd_probe_20260505_172101/latest.pth.tar` | D 保留 latest；完整 8 epoch run 從 H 恢復 |
| 守門 KD 邊界驗證 | `results/boundary_recon_guarded_kd_probe/` | `latest` 權重的未看過邊界驗證結果 |
| 守門 KD 環形守門 | `results/ring_guard_guarded_kd_probe/` | `latest` 權重的本地三尺度環形守門結果 |
| 外部 GMF 影像與分數 | `results/external_gmf/` | 三個 R42 候選的外部送測影像、`GMF_score.txt` 與比較摘要 |
| 外部 GMF 總報告 | `reports/R42_EXTERNAL_COMPARE.md` | 三個 R42 候選對 COMBO 的外部 step_std 比較 |
| 訓練前景紀錄 | `results/r42_training_foreground_20260505_142255.log` | 兩個正式候選的訓練 transcript |
| 邊界驗證紀錄 | `results/r42_boundary_eval_20260505_1537.log` | 顯微邊界重建與評估 transcript |
| 環形守門紀錄 | `results/r42_ring_guard_20260505.log` | 本地環形重建與守門 transcript |
| 守門 KD 訓練紀錄 | `results/r42_guarded_kd_probe_train_20260505_172058_stdout.log` | 守門 KD 短訓練紀錄 |

## 注意事項

- R42 是研究優先，不是預設升級候選。
- 文件以繁體中文為主。
- 本輪結果是研究成功但不可升級；外部補測後也不建議作顯微專用量測替代。
- 低比例權重平均與守門 KD 補測都沒有產生升級候選；下一步應改做通用邊界位置一致性，而不是單純增加 COMBO 混合或靜態老師牽引。
