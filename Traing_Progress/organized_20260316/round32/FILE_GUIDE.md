# Round 32（早期稽核）：正式紀錄在 Experiments/R32Sandbox

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [**R32 正式閱讀卡**](<../../../Experiments/R32Sandbox/FILE_GUIDE.md>) · [前一輪 Round 31](<../round31/FILE_GUIDE.md>)

**一句話：** 這裡保存的是 R32 領域容量研究在 2026-03-18 傍晚到 03-19 凌晨的早期報告：一份三候選的家族摘要（`r32_long_from_r25`、`r32_wider_b1`、`r32_real_eq_finetune`）與四份 `r32_long_from_r25` 的 0.8 px 稽核。R32 的正式治理、最終決策（03-19 傍晚）與外部結果都在 [`Experiments/R32Sandbox/`](<../../../Experiments/R32Sandbox/FILE_GUIDE.md>)，那裡才是 R32 的入口。

| | |
|---|---|
| 結果 | 見 [R32 正式閱讀卡](<../../../Experiments/R32Sandbox/FILE_GUIDE.md>)（時間線：未採用，內部通過、外部 0.8 px 退步 97.7%） |
| 時間 | 2026-03-18～03-19 凌晨（這裡的部分） |
| 實驗條件 | A：環形影像 0.8 px 的內部稽核 |
| 起點 | `r32_long_from_r25` 從 R25 的種子出發 |

## 讀這些內容要知道的事

1. **這裡的家族摘要有缺值**：三個候選的中心、步長欄位都是 `nan`，`r32_real_eq_finetune` 的家族分數是 −inf，代表當時這批結果還不完整，不要拿來判斷。
2. `r32_long_from_r25` 在稽核裡的最佳保存點仍是第 0 輪（中心 0.1183、步長 0.1166）。
3. 這個資料夾在操作指南裡明確不屬於早期輪次的治理範圍，只當作歷史資料與執行橋接。

## 原始報告

[領域容量摘要](<selected/reports/ROUND32_DOMAIN_CAPACITY_SUMMARY_20260318_185125.md>)；0.8 px 稽核四份在 [selected/reports/](<selected/reports>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round32.md>)。
