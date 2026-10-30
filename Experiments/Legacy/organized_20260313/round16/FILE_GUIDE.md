# Round 16 EDGEFIT：換成邊緣重心的幾何估計

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [下一輪 Round 17](<../round17/FILE_GUIDE.md>)

**一句話：** 2026-03-12 的早期調參輪。核心改動是把幾何估計從之前的代數擬合（`algebraic_fit`）換成邊緣重心（`edge_centroid`），四個候選裡選了 `r16_edge_highcenter` 部署。結果是中心誤差明顯下降，但步長誤差退步到超過硬閾值；這一輪的意義是證明邊緣重心比舊路線更適合當後續主線。

| | |
|---|---|
| 結果 | **研究候選**（當輪內部勝出，之後被 Round 17、18 取代） |
| 時間 | 2026-03-12 |
| 實驗條件 | A：環形影像三個尺度（0.08、0.8、8 px）的內部序列評分；這一輪沒有外部 GMF |
| 起點 | 沿用當時的 GeoEdgeAlignSR 訓練線 |

## 候選與選法

先用 0.8 px 的中心穩定性排序，再用 8 px 不退步當關卡、0.08 px 當次要依據；部署用的保存點再由「中心鎖定稽核」在三個尺度的保存點裡挑。

| 候選 | 綜合分數 | 部署分數 | 選中的保存點 |
|---|---:|---:|---|
| **r16_edge_highcenter** | 219.783 | −219.339 | 8 px 那個 |
| r16_algfit_pure | 228.202 | −228.268 | 0.08 px 那個 |
| r16_algfit_driftfocus | 228.383 | −229.616 | 0.08 px 那個 |
| r16_algfit_lightmono | 222.699 | −229.754 | 0.08 px 那個 |

## 讀這些數字要知道的事

1. **綜合分數第一名（`algfit_driftfocus`）不是部署選中的那個**；部署看的是稽核後的部署分數。這正是時間線上 R12～R15 那個「初排第一名和最後該採用的可能不同」的教訓。
2. 這些分數是當時內部評分的組合值，不是外部 GMF 的結果，不能跟後面輪次的外部數字直接比。

## 拿資料與重做

可重做程度：**partial**。選定的訓練紀錄（各尺度的 monitor 與 attribution 日誌）、稽核報告都在，但重跑仍要依賴這個資料夾以外的舊訓練工具。選定種子是 `selected/current_edgefit_seed.json`（不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡）。

## 原始報告

[多尺度摘要](<selected/reports/ROUND16_EDGEFIT_MULTISCALE_SUMMARY_20260312_090623.md>)、[檢查點稽核摘要](<selected/reports/ROUND16_EDGEFIT_CHECKPOINT_AUDIT_SUMMARY_20260312_090623.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../../docs/reproducibility/experiments/legacy__round16.md>)。
