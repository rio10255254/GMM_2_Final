# Round 28：步長權重往下掃（低於 0.35）

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 27](<../round27/FILE_GUIDE.md>) · [外部比較 R18～R28](<../external_compare_r18_r22_r25_r26_r27_r28/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_SUMMARY.md>) · [下一輪 Round 29](<../round29/FILE_GUIDE.md>)

**一句話：** 2026-03-16 深夜，測試 R26 的步長權重 0.35 是否偏高：往下試 0.30、0.32、0.33，選中 `r28_sm030`（內部中心 0.0825、步長 0.0684）。外部 GMF 的 0.8 px 步長標準差 0.2282，明顯比 R26 的 0.1913 差，三個尺度都退步。往下掃這個方向被否定，R26 維持基線。

| | |
|---|---|
| 結果 | **未採用**（否定性驗證：步長權重低於 0.35 外部退步） |
| 時間 | 2026-03-16 深夜 |
| 實驗條件 | A：環形影像，內部 0.8 px 稽核；外部 GMF 三尺度 |
| 起點 | R26 的路線 |

## 外部 GMF 步長標準差

| 尺度 | R26 sm035 | R28 sm030 |
|---|---:|---:|
| 8 px | **0.2010** | 0.2206 |
| 0.8 px | **0.1913** | 0.2282 |
| 0.08 px | **0.1803** | 0.1922 |

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_round28_step_mag_balance_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[步長平衡決策](<selected/reports/ROUND28_STEP_MAG_BALANCE_DECISION_20260316_225523.md>)、[步長平衡摘要](<selected/reports/ROUND28_STEP_MAG_BALANCE_SUMMARY_20260316_225344.md>)、[外部比較](<../external_compare_r18_r22_r25_r26_r27_r28/reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_SUMMARY.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round28.md>)。
