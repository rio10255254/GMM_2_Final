# Round 17 STEPFIX：直接修步長大小

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 16](<../round16/FILE_GUIDE.md>) · [下一輪 Round 18](<../round18/FILE_GUIDE.md>)

**一句話：** 2026-03-13 上午，沿著 Round 16 的邊緣重心路線，新增 `SEQ_STEP_MAG_WEIGHT` 直接修步長大小。部署選中 `r17_ec_stepmag`：步長誤差修回安全範圍，0.8 px 的中心誤差也壓到當時歷史最低附近，成為之後中心導向輪次的乾淨 0.8 px 基線。

| | |
|---|---|
| 結果 | **研究候選**（當輪內部勝出，之後被 Round 18 取代） |
| 時間 | 2026-03-13 上午 |
| 實驗條件 | A：環形影像三個尺度（0.08、0.8、8 px）的內部序列評分；沒有外部 GMF |
| 起點 | Round 16 的邊緣重心路線 |

## 候選與選法

| 候選 | 綜合分數 | 部署分數 | 選中的保存點 |
|---|---:|---:|---|
| **r17_ec_stepmag** | 350.388 | −119.067 | 8 px 那個 |
| r17_af_stepmag | 358.291 | −129.163 | 0.08 px 那個 |
| r17_ec_balanced | 350.216 | −130.425 | 0.08 px 那個 |
| r17_ec_gradboost | 350.177 | −130.425 | 0.08 px 那個 |

部署分數從 Round 16 的約 −219 大幅改善到 −119。

## 讀這些數字要知道的事

1. 綜合分數第一的 `af_stepmag`（代數擬合版）同樣不是部署選中的，選法跟 Round 16 一樣。
2. 綜合分數的尺度跟 Round 16 不同（16 約 220～228、17 約 350～358），兩輪不能直接拿綜合分數比；部署分數才是同一套規則下的比較。

## 拿資料與重做

可重做程度：**partial**。選定的訓練紀錄與稽核在，重跑要依賴舊工具與共用模型程式。選定種子 `selected/current_stepfix_seed.json`（不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡）。

## 原始報告

[多尺度摘要](<selected/reports/ROUND17_STEPFIX_MULTISCALE_SUMMARY_20260313_130618.md>)、[檢查點稽核摘要](<selected/reports/ROUND17_STEPFIX_CHECKPOINT_AUDIT_SUMMARY_20260313_130618.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../../docs/reproducibility/experiments/legacy__round17.md>)。
