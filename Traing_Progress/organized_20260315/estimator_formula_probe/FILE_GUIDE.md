# Estimator Formula Probe：soft_band 公式變體都沒過中尺度關卡

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一步 Branch E Follow-up](<../branch_e_followup/FILE_GUIDE.md>) · [接手的成對位移探針](<../pairwise_delta_probe/FILE_GUIDE.md>)

**一句話：** 2026-03-15 晚間，照 Branch E Follow-up 的建議，嘗試幾種 `soft_band_refine` 的公式變體（更銳利、混入步長、較輕），想在保住中心改善的同時把 0.8 px 步長壓到 0.45 以下。五個變體的中心誤差都大幅改善（約 0.17～0.38，控制組 6.97），但步長誤差全部在 0.58～0.84，沒有一個通過中尺度關卡。這條路之後由成對位移探針取代。

| | |
|---|---|
| 結果 | **未採用**（沒有變體通過校準後的中心加步長關卡；保留作沿革） |
| 時間 | 2026-03-15 晚間 |
| 實驗條件 | A：環形影像 0.8 px 的估計器稽核，使用 Round 18 的選定保存點；沒有外部 GMF |
| 起點 | 不訓練 |

## 結果

| 候選 | 中心誤差 | 步長誤差 | 通過中尺度關卡 |
|---|---:|---:|---|
| soft_band | 0.1862 | 0.5804 | 否 |
| soft_band_sharp | 0.1689 | 0.6700 | 否 |
| soft_band_stepmix | 0.3253 | 0.7121 | 否 |
| soft_band_light | 0.3845 | 0.7841 | 否 |
| soft_band_stepmix_sharp | 0.3091 | 0.8417 | 否 |
| edge_ctrl（控制組） | 6.9723 | 1.3555 | 否 |

8 px 的總體關卡（用 `edge_band_refine`）是通過的。

## 拿資料與重做

可重做程度：**historical-only**，只供稽核與沿革追查。

## 原始報告

[公式探針摘要](<selected/reports/ESTIMATOR_FORMULA_PROBE_SUMMARY_20260315_214018.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本面保存紀錄](<../../../docs/reproducibility/experiments/legacy__estimator_formula_probe.md>)。
