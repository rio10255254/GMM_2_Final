# Round 18 CENTERPUSH：再加重中心權重，成為當時採用的基線

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 17](<../round17/FILE_GUIDE.md>) · [下一輪 Round 19](<../round19/FILE_GUIDE.md>) · [跟 R22 的外部比較](<../../organized_20260316/external_compare_round18_round22/reports/EXTERNAL_COMPARE_R18_R22_SUMMARY.md>)

**一句話：** 2026-03-13 下午，延續 Round 17，進一步提高中心相關的權重。部署選中 `r18_ec_highcenter`：0.8 px 的中心誤差仍停在約 0.85 的平台沒突破，但整體部署分數最穩，所以成為外部比較時代之前正式採用的內部基線。之後在 `external_compare_round18_round22` 跟 Round 22 做外部比較。

| | |
|---|---|
| 結果 | **採用**（當時的內部基線；之後由 R22 的外部比較取代） |
| 時間 | 2026-03-13 下午 |
| 實驗條件 | A：環形影像三個尺度（0.08、0.8、8 px）的內部序列評分；這一輪另外保存了外部重建與 GMF 驗證資料 |
| 起點 | Round 17 的路線 |

## 候選與選法

| 候選 | 綜合分數 | 部署分數 | 選中的保存點 |
|---|---:|---:|---|
| **r18_ec_highcenter** | 350.209 | −112.256 | 8 px 那個 |
| r18_ec_stepmag_up | 350.254 | −112.580 | 8 px 那個 |
| r18_ec_balanced | 350.213 | −117.199 | 8 px 那個 |
| r18_af_highcenter | 358.186 | −123.994 | 0.8 px 那個 |

選中候選在三個保存點上的稽核分數（0.08／0.8／8 px）：8 px 那個是 17.949／8.762／22.527，另兩個都是 13.734／8.000／21.898。

## 讀這些數字要知道的事

1. **「0.8 px 中心誤差約 0.85 的平台」出自本批次 README 的總結**，這份資料夾的稽核表只有綜合分數。
2. 批次 README 的判讀：到這裡，8 px 與步長誤差大致已控制住，真正沒解掉的是 0.8 px（0.1 µm）環形的絕對中心穩定性。

## 拿資料與重做

可重做程度：**partial**。選定訓練紀錄、報告與外部驗證資料都保存了，但重跑仍要依賴主專案工具與歷史權重。選定種子 `selected/current_centerpush_seed.json`（不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡）。

## 原始報告

[多尺度摘要](<selected/reports/ROUND18_CENTERPUSH_MULTISCALE_SUMMARY_20260313_142259.md>)、[檢查點稽核摘要](<selected/reports/ROUND18_CENTERPUSH_CHECKPOINT_AUDIT_SUMMARY_20260313_142259.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round18.md>)。
