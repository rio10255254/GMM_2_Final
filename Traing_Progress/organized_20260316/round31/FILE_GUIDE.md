# Round 31：在 R30 上調訓練權重與等化訊號

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 30](<../round30/FILE_GUIDE.md>) · [之後的 R32](<../../../Experiments/R32Sandbox/FILE_GUIDE.md>)

**一句話：** 2026-03-18 在 `r30_b1_dironly` 上做 B1 的超參數調整，四個候選（等化機率提高、等化權重提高、兩者合併、邊緣比例降低）。四個候選的內部指標完全相同，選了 `r31_eq_prob_up`。外部 GMF 量到的三個候選在 0.8 px 都比 R30 差（退步 6.8%～10.5%），所以 R30 維持正式基準。

| | |
|---|---|
| 結果 | **未採用**（外部全部退步） |
| 時間 | 2026-03-18 決策；03-19 外部比較 |
| 實驗條件 | A：環形影像，內部 0.8 px 稽核；外部 GMF 三尺度 |
| 起點 | R30 的 `r30_b1_dironly` |

## 外部 GMF 步長標準差（0.8 px）

| 候選 | 步長標準差 | 相對 R30 |
|---|---:|---:|
| r30_b1_dironly | **0.1679** | — |
| r31_eq_prob_up | 0.1849 | +10.1% |
| r31_eq_weight_up | 0.1855 | +10.5% |
| r31_edge_ratio_low | 0.1793 | +6.8% |

## 讀這些數字要知道的事

1. **四個候選的內部指標逐位相同**，內部篩選根本分不出來，只能靠外部。
2. **`r31_eq_combo` 缺 `GMF_score.txt`**，報告把它當成外部檔案缺件，不算量測到的退步，也不列入比較。
3. 8 px 與 0.08 px 上 `eq_prob_up` 其實比 R30 好，但決策主軸是 0.8 px。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_round31_b1_hyperparam_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[外部比較](<selected/reports/ROUND31_EXTERNAL_COMPARE.md>)、[超參數決策](<selected/reports/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md>)、[超參數摘要](<selected/reports/ROUND31_B1_HYPERPARAM_SUMMARY_20260318_113707.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round31.md>)。
