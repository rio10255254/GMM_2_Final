# Round 25：從零訓練加入絕對中心，第一次外部突破

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 24](<../round24/FILE_GUIDE.md>) · [外部比較 R18／R22／R25](<../external_compare_r18_r22_r25/reports/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.md>) · [下一輪 Round 26](<../round26/FILE_GUIDE.md>)

**一句話：** R23、R24 的微調都沒動，2026-03-16 傍晚改成從零訓練、一開始就加入絕對中心要求，三種權重（sw005、sw010、sw020）。選中 `r25_sw010`（內部中心 0.0938、步長 0.0953），外部 GMF 的 0.8 px 步長標準差第一次明顯低於 R18 與 R22h：0.212 對 0.285，三個尺度都較好。

| | |
|---|---|
| 結果 | **研究候選**（第一次外部突破，接著由 Round 26 取代） |
| 時間 | 2026-03-16 傍晚 |
| 實驗條件 | A：環形影像，內部 0.8 px 稽核；外部 GMF 三尺度（NTU Pitch 1、0.1、0.01 µm） |
| 起點 | 隨機初始化（從零訓練） |

## 外部 GMF 步長標準差

| 尺度 | R18 | R22 hold | **R25 sw010** |
|---|---:|---:|---:|
| 8 px（1 µm） | 0.2507 | 0.2887 | **0.2115** |
| 0.8 px（0.1 µm） | 0.2855 | 0.2855 | **0.2120** |
| 0.08 px（0.01 µm） | 0.2094 | 0.1893 | **0.1648** |

## 讀這些數字要知道的事

1. **比較報告的自動結論寫的是「維持 R22h」。** 那份報告除了步長標準差，還要求 0.8 px 的錨點滯後一階自相關至少 0.10，R25 只有 0.021，所以自動建議不升級。之後補寫的批次 README 與操作指南則把它定位成「第一次外部突破」。兩種說法都保留在原檔；實際上下一份比較（R26 是否取代 R25）就把 R25 當作要超越的對象。
2. **R18 與 R22h 在 0.8 px 幾乎一樣**（0.2855），這是上一份 R18 對 R22 比較的結果，所以這裡兩者都列為舊基線。

## 拿資料與重做

可重做程度：**partial**。外部比較的重建與 GMF 分數保存在 `../external_compare_r18_r22_r25/r25_sw010/`。選定種子 `selected/current_round25_scratch_abs_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[從零絕對中心決策](<selected/reports/ROUND25_SCRATCH_ABS_DECISION_20260316_175528.md>)、[從零絕對中心摘要](<selected/reports/ROUND25_SCRATCH_ABS_SUMMARY_20260316_175340.md>)、[外部比較](<../external_compare_r18_r22_r25/reports/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round25.md>)。
