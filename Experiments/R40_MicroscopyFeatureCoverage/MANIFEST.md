# R40 Manifest

Round:R40

實驗目錄:`Experiments/R40_MicroscopyFeatureCoverage/`

分支:`sandbox/r40`

狀態:訓練、local 分析、外部 GMF 都完成。R40 是研究用 capacity 結果,不是升級候選。

## 目的

量受控合成 microscopy 特徵能不能把重建清晰度推得比 COMBO 與 R39 a030 高。

## 主要 script

- `scripts/r40_micro_data.py` — 產乾淨 microscopy label、驗 source/label 配對、build train/validation 包。
- `scripts/launch_r40.py` — 啟動兩個 capacity 候選,透過 `trainer.MODEL_NAME_BASE` 保住 artifact identity。
- `scripts/run_r40_micro_recon.py` 與 `scripts/r40_micro_metrics.py` — 跑 unseen microscopy 特徵驗證集並彙總指標。
- `scripts/run_r40_ring_guard.py` — 跑既有的 720-angle local ring guard。
- `scripts/run_r40_weight_sweep.py` — 搜 COMBO ↔ R40 的權重平均空間。
- `scripts/r40_external_compare.py` — parse 最終的外部 GMF 檔案。

## 資料包

預設包根目錄:

`Training_Data/r40_microscopy_feature_coverage/`

Profile:

| Profile | 角色 |
|---------|------|
| `r40_micro_capacity_train` | 兩個 R40 候選的訓練包 |
| `micro_val_unseen` | held-out microscopy 特徵驗證包 |

build 後的包:

| Profile | 配對總數 | 內容 |
|---------|--------:|------|
| `r40_micro_capacity_train` | 1300 | ring replay、R39 shape replay、R40 microscopy 特徵 |
| `micro_val_unseen` | 100 | held-out microscopy 特徵驗證 |

Baseline 彙總:

- `results/micro_recon/combo_micro_summary.json`
- `results/micro_recon/a030_micro_summary.json`
- `results/micro_recon/r40_baseline_micro_comparison.png`

訓練後彙總:

- `results/micro_recon_trained/a030_best_summary.json`
- `results/micro_recon_trained/combo_best_summary.json`
- `results/micro_recon_trained/a030_latest_summary.json`
- `results/micro_recon_trained/combo_latest_summary.json`
- `results/ring_guard/r40_a030_best_ring_guard_summary.json`
- `results/ring_guard/r40_combo_best_ring_guard_summary.json`
- `results/ring_guard/r40_a030_latest_ring_guard_summary.json`
- `results/ring_guard/r40_combo_latest_ring_guard_summary.json`
- `results/weight_sweep/combo_best_low_alpha/micro_recon/a045_micro_summary.json`
- `results/weight_sweep/combo_best_low_alpha/ring_guard/a045_ring_guard_summary.json`
- `results/weight_sweep/combo_best_low_alpha/r40_a045_micro_comparison_sheet.png`
- `results/external_gmf/external_compare_summary.json`
- `results/external_gmf/step_audit/step_audit_summary.json`
- `results/external_gmf/step_audit/pitch8px_steps.csv`
- `results/external_gmf/step_audit/pitch0p8px_steps.csv`
- `results/external_gmf/step_audit/pitch0p08px_steps.csv`

目前的 local guarded 候選:

- `results/weight_sweep/combo_best_low_alpha/checkpoints/a045/best_tradeoff.pth.tar`

## 升級邊界

R40 訓練 endpoint 是 capacity 探針,預設不是升級候選。要進入正式專案狀態更新,候選或權重平均必須:形狀指標進步、microscopy 特徵驗證進步、且通過外部三尺度 ring GMF。

目前狀態:`r40_combo_best_avg_a045` 過了 local 三尺度 ring guard,在 held-out microscopy 特徵上也比 COMBO 與 R39 a030 強,但外部 GMF 在 8px guard 上退步 +22.80% vs COMBO。沒做任何正式 baseline 或 approved alternate 更新。
