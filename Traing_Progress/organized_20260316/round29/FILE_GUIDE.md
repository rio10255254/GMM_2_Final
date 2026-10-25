# Round 29：步長權重往上掃（高於 0.35）

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 28](<../round28/FILE_GUIDE.md>) · [外部比較 R18～R29](<../external_compare_r18_r22_r25_r26_r27_r28_r29/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.md>) · [下一輪 Round 30](<../round30/FILE_GUIDE.md>)

**一句話：** 2026-03-17 補做另一側：步長權重往上試 0.38、0.40、0.42，選中 `r29_sm042`（內部中心 0.0682、步長 0.0789），內部通過。外部 GMF 的 0.8 px 步長標準差 0.2173，仍差於 R26 的 0.1913；只有 0.08 px 明顯較好。結論是 R26 的 0.35 就是這個權重的最佳點，單純調步長權重已經沒有空間，下一步要改架構。

| | |
|---|---|
| 結果 | **未採用**（否定性驗證：步長權重高於 0.35 外部也沒贏） |
| 時間 | 2026-03-17 |
| 實驗條件 | A：環形影像，內部 0.8 px 稽核；外部 GMF 三尺度 |
| 起點 | R26 的路線 |

## 外部 GMF 步長標準差

| 尺度 | R26 sm035 | R29 sm042 |
|---|---:|---:|
| 8 px | **0.2010** | 0.2054 |
| 0.8 px | **0.1913** | 0.2173 |
| 0.08 px | 0.1803 | **0.1375** |

## 讀這些數字要知道的事

1. **R29 的 0.8 px 數字剔除過一個離群步長。** 這份比較用的是 3σ 規則（|步長 − 平均| > 3 倍標準差），剔除前是 0.2348、剔除後 0.2173；其他模型在這裡都沒有被剔除。專案後來改成外部 GMF 一律用原始步長標準差、只剔除 z > 5 的 GMF 失敗點，所以這個數字不能直接跟後期的報告比。不論剔不剔除，結論都一樣是沒贏 R26。
2. 比較報告註記 `r29_winner` 目錄名稱要在訓練後手動改成實際 winner 名稱。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_round29_step_mag_upper_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[上掃決策](<selected/reports/ROUND29_STEP_MAG_UPPER_DECISION_20260317_124715.md>)、[上掃摘要](<selected/reports/ROUND29_STEP_MAG_UPPER_SUMMARY_20260317_115029.md>)、[外部比較](<../external_compare_r18_r22_r25_r26_r27_r28_r29/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round29.md>)。
