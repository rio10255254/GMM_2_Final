# Round 24：單幀線上的絕對中心微調（診斷）

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [同日的 Round 23](<../round23/FILE_GUIDE.md>) · [下一輪 Round 25](<../round25/FILE_GUIDE.md>)

**一句話：** 2026-03-16 下午，跟 Round 23 平行：改從單幀那條線做絕對中心微調，三種權重（0.10、0.30、0.50）。三個候選的內部數字同樣完全相同（中心 0.1508、步長 0.0783），跟 R22 的 `hold` 一致，表示最佳保存點沒有往前推。只是診斷，沒有升級。

| | |
|---|---|
| 結果 | **未採用**（診斷性負結果：微調沒有移動模型） |
| 時間 | 2026-03-16 下午 |
| 實驗條件 | A：環形影像 0.8 px 的內部稽核（8 px 為總體關卡） |
| 起點 | R22 `hold` 那一系的單幀線 |

## 讀這些數字要知道的事

R23 與 R24 兩條線的微調都沒有讓模型離開起點，所以下一輪改成[從零訓練並一開始就加入絕對中心要求](<../round25/FILE_GUIDE.md>)。

## 拿資料與重做

可重做程度：**historical-only**。選定種子 `selected/current_round24_single_abs_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[單幀絕對中心決策](<selected/reports/ROUND24_SINGLE_ABS_DECISION_20260316_163357.md>)、[單幀絕對中心摘要](<selected/reports/ROUND24_SINGLE_ABS_SUMMARY_20260316_163227.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../../docs/reproducibility/experiments/legacy__round24.md>)。
