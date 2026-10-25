# 2026-03-09 批次：第一次外部 GMF 驗證，以及 R5～R6

[研究時間線](<../../docs/research/TIMELINE.md>) · [早期輪次對照](<../../docs/reproducibility/lineage/EARLY_ROUNDS.md>) · [前一個批次 3/07](<../organized_20260307/FILE_GUIDE.md>) · [下一個批次 3/10](<../organized_20260310/FILE_GUIDE.md>)

**一句話：** 從 3/09 起，外部驗證有了自己的入口。第一份結果是 3/07 種子 `step8_curve_stdguard_v2` 在 NTU Pitch 1 µm（8 px）資料上的外部 GMF：99 個步長的平均 8.021 px、標準差 0.219 px、P05～P95 跨度 0.675 px。之後的 R5（保留外部行為）與 R6（多尺度長跑）也收在這裡；R6 的重要教訓是最後階段的長訓練一再破壞前面的好結果，「訓練更久」不可靠。

| | |
|---|---|
| 結果 | **分析**（建立外部 GMF 驗證流程與第一份基準；R5、R6 未採用） |
| 時間 | 2026-03-09～03-10 |
| 實驗條件 | A：NTU Pitch 1 µm 資料集的外部 GMF（8 px 步長）；R6 另有多尺度內部長跑 |
| 起點 | 3/07 的 `step8_curve_stdguard_v2` 種子 |

## 第一份外部 GMF（stdguard_v2，8 px）

| 項目 | 數值 |
|---|---:|
| 步長數 | 99 |
| 平均步長 | 8.021 px |
| 標準差 | 0.219 px |
| P05～P95 跨度 | 0.675 px |
| 最小／最大 | 7.450／8.623 px |

## 讀這些內容要知道的事

1. **步長的正負號**：報告定義 `step_i = POSY(i) − POSY(i+1)`，帶正負號的平均是 −8.021 px。
2. **R5、R6 的編號是事後從原日誌串回的**，原 profile 名稱含 `extval` 不代表當次取得了新的外部驗收；詳見[早期輪次對照](<../../docs/reproducibility/lineage/EARLY_ROUNDS.md>)。
3. **大型內容已移到 H 槽**（2026-08-01）：完整 295 個檔、1.72 GiB 在 H 槽快照；D 槽保留外部 GMF 原始與分析結果、視覺比較與精選摘要。恢復方式見 [ARCHIVE_POINTER](<ARCHIVE_POINTER.md>)。

## 原始報告

[外部 GMF 步長統計](<external_validation/current_seed/reports/GMF_POSY_step_stats_current_seed_20260309.md>)、[外部驗證說明](<external_validation/current_seed/README.md>)、`pending/reports/` 下的自動調參與長跑結果、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本批次保存紀錄](<../../docs/reproducibility/experiments/legacy__organized_20260309.md>)。
