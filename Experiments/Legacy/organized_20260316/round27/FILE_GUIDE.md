# Round 27：內部最好，外部沒贏 R26

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 26](<../round26/FILE_GUIDE.md>) · [外部比較 R18～R27](<../external_compare_r18_r22_r25_r26_r27/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_SUMMARY.md>) · [下一輪 Round 28](<../round28/FILE_GUIDE.md>)

**一句話：** 2026-03-16 晚間，在 R26 之後繼續調步長權重（0.25、0.28、0.30），選中 `r27_sm028`：內部中心 0.0603、步長 0.0737，都比 R26 好，是 R26 時代的內部最前緣。但外部 GMF 的 0.8 px 步長標準差 0.1963，略差於 R26 的 0.1913，所以維持 R26。

| | |
|---|---|
| 結果 | **未採用**（內部最前緣，外部主戰場沒超越 R26） |
| 時間 | 2026-03-16 晚間 |
| 實驗條件 | A：環形影像，內部 0.8 px 稽核；外部 GMF 三尺度 |
| 起點 | R26 的路線 |

## 外部 GMF 步長標準差

| 尺度 | R26 sm035 | R27 sm028 |
|---|---:|---:|
| 8 px | 0.2010 | **0.1980** |
| 0.8 px | **0.1913** | 0.1963 |
| 0.08 px | 0.1803 | **0.1724** |

## 讀這些數字要知道的事

內部數字更好、外部 0.8 px 卻略差，是 R22 那個「內部與外部脫節」的又一個例子。R27 的錨點自相關 0.353 反而是當時最高。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_round27_step_mag_recovery_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[步長恢復決策](<selected/reports/ROUND27_STEP_MAG_RECOVERY_DECISION_20260316_204452.md>)、[步長恢復摘要](<selected/reports/ROUND27_STEP_MAG_RECOVERY_SUMMARY_20260316_204323.md>)、[外部比較](<../external_compare_r18_r22_r25_r26_r27/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_SUMMARY.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../../docs/reproducibility/experiments/legacy__round27.md>)。
