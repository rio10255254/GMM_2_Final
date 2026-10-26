# Round 23：pairmix 線上的絕對中心微調（診斷）

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 22](<../../organized_20260315/round22/FILE_GUIDE.md>) · [同日的 Round 24](<../round24/FILE_GUIDE.md>)

**一句話：** 2026-03-16 下午，R22 在外部沒贏 R18 之後的第一個嘗試：在 pairmix 估計器上加一個錨點一致性要求，用三種權重（0.03、0.05、0.10）微調。三個候選的內部數字完全相同，也跟 R22 的 `stepguard` 幾乎一樣（中心 0.1845、步長 0.0658），表示微調沒有把最佳保存點往前推。只是診斷，沒有升級，也沒有做外部比較。

| | |
|---|---|
| 結果 | **未採用**（診斷性負結果：微調沒有移動模型） |
| 時間 | 2026-03-16 下午 |
| 實驗條件 | A：環形影像 0.8 px 的內部稽核（8 px 為總體關卡） |
| 起點 | R22 的 pairmix 線 |

## 讀這些數字要知道的事

1. **三個權重得到逐位相同的結果**，加上數字等於 R22 起點，這通常代表最佳保存點仍是起始狀態，新要求沒有實際改變模型。
2. 跟 [Round 24](<../round24/FILE_GUIDE.md>) 一起看：一個從 pairmix 線、一個從單幀線做同樣的絕對中心微調，兩者都沒動，所以下一步改成[從零訓練](<../round25/FILE_GUIDE.md>)。

## 拿資料與重做

可重做程度：**historical-only**。選定種子 `selected/current_round23_anchor_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[錨點一致性決策](<selected/reports/ROUND23_ANCHOR_CONSISTENCY_DECISION_20260316_155400.md>)、[錨點一致性摘要](<selected/reports/ROUND23_ANCHOR_CONSISTENCY_SUMMARY_20260316_155229.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round23.md>)。
