# Round 26：調步長權重，升為基線 r26_sm035

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 25](<../round25/FILE_GUIDE.md>) · [外部比較 R18～R26](<../external_compare_r18_r22_r25_r26/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md>) · [下一輪 Round 27](<../round27/FILE_GUIDE.md>) · [之後的新 PSF 重訓 R26NewPSFCheck](<../../../Experiments/R26NewPSFCheck/FILE_GUIDE.md>)

**一句話：** 2026-03-16 晚間，在 R25 的路線上恢復步長：步長權重試 0.25、0.30、0.35，選中 `r26_sm035`（內部中心 0.0691、步長 0.0857）。外部 GMF 的 0.8 px 步長標準差從 R25 的 0.212 再降到 0.191，錨點自相關 0.226 也過了 0.10 的門檻，報告建議升級。`r26_sm035` 成為新的基線，也是 R26 正式交付包的模型，直到 R30 取代。

| | |
|---|---|
| 結果 | **採用**（基線 `r26_sm035`；之後由 R30 取代） |
| 時間 | 2026-03-16 晚間 |
| 實驗條件 | A：環形影像，內部 0.8 px 稽核；外部 GMF 三尺度 |
| 起點 | R25 的從零訓練路線 |

## 外部 GMF 步長標準差

| 尺度 | R18 | R25 sw010 | **R26 sm035** |
|---|---:|---:|---:|
| 8 px | 0.2507 | 0.2115 | **0.2010** |
| 0.8 px | 0.2855 | 0.2120 | **0.1913** |
| 0.08 px | 0.2094 | **0.1648** | 0.1803 |

## 讀這些數字要知道的事

1. **0.08 px 是 R25 較好**，但決策主軸是 0.8 px。
2. **3/26 曾用新 PSF 重訓這個交付包的模型**，那次退步的原因與新 PSF 升為標準的過程記在 [R26NewPSFCheck](<../../../Experiments/R26NewPSFCheck/FILE_GUIDE.md>)。
3. 同一個基線之後也被拿來做 [TTA 測試](<../tta_experiment/FILE_GUIDE.md>)，結果 0.8 px 反而變差。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_round26_step_recovery_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。R26 正式交付包在 `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/`；2026-10-26 的全專案掃描顯示其中約 5.6 GB 在雲端找不到同內容。

## 原始報告

[步長恢復決策](<selected/reports/ROUND26_STEP_RECOVERY_DECISION_20260316_191450.md>)、[步長恢復摘要](<selected/reports/ROUND26_STEP_RECOVERY_SUMMARY_20260316_191318.md>)、[外部比較](<../external_compare_r18_r22_r25_r26/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round26.md>)。
