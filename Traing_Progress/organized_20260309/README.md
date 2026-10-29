# 20260309 測試與外部驗證入口

## 這個資料夾的定位

`Traing_Progress/organized_20260309/` 從 2026-03-09 開始，專門收：

- 今天之後的新外部驗證
- 今天之後的新自動化測試與續跑
- 與今天驗證結果直接相關的報告

這樣劃分後：

- `organized_20260307/`
  - 主要保留前一階段的內部 seed 搜索與 autotune 歷史
- `organized_20260309/`
  - 主要保留今天起的外部驗證與後續新測試

## 目前外部驗證主入口

- [external_validation/current_seed/README.md](external_validation/current_seed/README.md)
- [external_validation/current_seed/CURRENT_TARGET.json](external_validation/current_seed/CURRENT_TARGET.json)

目前驗證對象：

- 來源 seed：
  - `Traing_Progress/organized_20260307/selected/current_seed.json`
- seed label：
  - `step8_curve_stdguard_v2`
- 實際權重：
  - `Traing_Progress/organized_20260307/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar`

## 目前已保存的外部驗證結果

這次 `GMF_score.txt` 與 `POSY` 步長分析已經保存於：

- raw：
  - `external_validation/current_seed/gmf_results/raw/GMF_score.txt`
- analyzed：
  - `external_validation/current_seed/gmf_results/analyzed/GMF_POSY_step_stats_current_seed_20260309.md`
  - `external_validation/current_seed/gmf_results/analyzed/GMF_POSY_step_stats_current_seed_20260309.json`
- report copy：
  - `external_validation/current_seed/reports/GMF_POSY_step_stats_current_seed_20260309.md`

## 接下來的用途

這個資料夾接下來會同時承接兩件事：

1. 保存今天這次外部驗證結果，作為後續比較基準
2. 收後續新一輪訓練 / autotune / external GMF 驗證的結果

## 2026-08-01 storage note

This is now a historical external-validation batch. Its complete pre-cleanup snapshot is stored at:

`H:\GMM_2_Final_Archive\legacy\organized_20260309\20260801_full_history\snapshot`

D drive retains the external GMF evidence, visual comparisons, selected summaries, and small pending records. The large `rejected/` candidate package is retained in the verified H-drive snapshot. See `MANIFEST.md` and `ARCHIVE_POINTER.md`.
