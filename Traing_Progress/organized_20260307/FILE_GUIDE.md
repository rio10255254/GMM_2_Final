# 2026-03-07 批次：R1（以及 3/09 的 R2～R4 紀錄）

[研究時間線](<../../docs/research/TIMELINE.md>) · [早期輪次對照](<../../docs/reproducibility/lineage/EARLY_ROUNDS.md>) · [前一個批次 3/06](<../organized_20260306/FILE_GUIDE.md>) · [下一個批次 3/09](<../organized_20260309/FILE_GUIDE.md>)

**一句話：** 3/06 基準版之後的新測試區。R1 把選模改成直接看 8 px 步長、極端值與平均偏移，並新增稀疏曲邊的資料階段（stage 15、16）。內部最好的 sweep 候選 `step8_curve_stdguard_v2` 被保留成後續續訓的種子，但它**不是**當時手動推論的正式版，正式比較基準仍是 3/06 的 `step8_curve_sharp`。`pending/` 裡另有 3/09 R2～R4 的自動調參結果紀錄。

| | |
|---|---|
| 結果 | **研究候選**（R1 產生後來的內部種子 `stdguard_v2`，不是當時的外部正式版；R2～R5 都沒取得新的外部通過） |
| 時間 | 2026-03-07（R1）；`pending/reports` 裡有 03-09 的 R2～R4 紀錄 |
| 實驗條件 | A：內部 8 px 步長評分；外部 GMF 由使用者手動跑 NTU Pitch 1 µm 資料集（200 張中的奇數張） |
| 起點 | 3/06 的 `step8_curve_sharp` |

## 讀這些內容要知道的事

1. **R1 保留了幾個失敗**：Windows 長路徑、選模視窗與日誌不同步（見[早期輪次對照的 R1](<../../docs/reproducibility/lineage/EARLY_ROUNDS.md>)）。
2. **R2～R4 的編號是事後從原日誌串回的**：`pending/reports/AUTO_TUNE_RESULT_20260309_134617` 是 R4（保守精修）、`_144411` 與 `_151919` 是 R3 的兩個 profile（GMF 保護、兼顧銳利度）。原報告本身沒寫 R 號，對照依據見[早期輪次對照](<../../docs/reproducibility/lineage/EARLY_ROUNDS.md>)。
3. **當時的分工**：模型重建、統計與整理由助理做；外部 GMF 定位程式在助理的工作區之外，由使用者手動執行後提供 `GMF_score.txt`。評估主目標是 POSY 步長平均接近 8 px、標準差盡量小。
4. **大型內容已移到 H 槽**（2026-08-01）：完整 440 個檔、4.37 GiB 在 H 槽快照；D 槽只留 `selected/` 的代表模型與種子、少量紀錄。恢復方式見 [ARCHIVE_POINTER](<ARCHIVE_POINTER.md>)。

## 原始報告

[R1 自動調參進度](<selected/reports/AUTO_TUNE_ROUND1_20260307.md>)、[R1 整理報告](<ROUND1_CLEANUP_REPORT_20260309.md>)、[以 3/06 為基準的說明](<BASELINE_FROM_20260306.md>)、[3/09 重啟的自動調參鏈計畫](<pending/reports/AUTO_TUNE_CHAIN_PLAN_20260309_RESTART.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本批次保存紀錄](<../../docs/reproducibility/experiments/legacy__organized_20260307.md>)。
