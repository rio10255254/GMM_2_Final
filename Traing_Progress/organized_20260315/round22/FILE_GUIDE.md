# Round 22：pairmix_algblend 通過內部關卡，外部 GMF 卻沒贏 Round 18

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [來源 Pairwise Delta Probe](<../pairwise_delta_probe/FILE_GUIDE.md>) · [跟 R18 的外部比較](<../../organized_20260316/external_compare_round18_round22/reports/EXTERNAL_COMPARE_R18_R22_SUMMARY.md>) · [下一輪 Round 23](<../../organized_20260316/round23/FILE_GUIDE.md>)

**一句話：** 2026-03-15 深夜，驗證 `pairmix_algblend`（單幀錨點加成對位移估計器）在正式的 0.8 px 訓練探針裡，能不能同時保住絕對中心與成對步長。三個候選都通過了校準後的中尺度加總體關卡，正式選定 `r22_pairmix_stepguard`（中心 0.1845、步長 0.0657）。這是第一個正式通過 pairmix 內部關卡的訓練輪。但 3/16 的外部 GMF 比較中，它在 0.8 px 主戰場沒有贏過 Round 18（`stepguard` 的步長標準差 0.2855→0.3336、退步 16.8%；`hold` 跟 Round 18 持平），所以不升級。內部中心誤差改善 4.6 倍、外部反而退步，報告稱這是當時「最關鍵的新發現」：內部指標與外部 GMF 之間有根本性的脫節。

| | |
|---|---|
| 結果 | **未採用**（通過內部 pairmix 關卡；外部 GMF 在 0.8 px 沒有超越 Round 18，不升級） |
| 時間 | 2026-03-15 深夜（事後檢討更新到 03-16） |
| 實驗條件 | A：環形影像，只跑 0.8 px（8 px 為總體關卡，0.08 px 只記錄不擋）；之後由 `organized_20260316` 做外部重建與 GMF |
| 起點 | Round 18 的 `r18_ec_highcenter` |

## 結果

| 候選 | 中尺度中心 | 中尺度步長 | 8 px 步長 | 8 px 方向正確率 | 最終 |
|---|---:|---:|---:|---:|---|
| **r22_pairmix_stepguard**（正式選定） | 0.1845 | 0.0657 | 0.1155 | 0.8157 | 通過 |
| r22_pairmix_consistency | 0.1845 | 0.0657 | 0.1155 | 0.8157 | 通過 |
| r22_pairmix_hold | **0.1508** | 0.0768 | 0.1140 | 0.8271 | 通過 |

## 讀這些數字要知道的事

1. **原始家族排名與單看中尺度的稽核其實都偏好 `hold`**（中心更好），正式選定卻是 `stepguard`（步長更好），因為當時的決策鏈偏保守、步長優先。報告把這個差異明白寫出來，沒有藏。
2. **外部比較的結果**（[R18 對 R22](<../../organized_20260316/external_compare_round18_round22/reports/EXTERNAL_COMPARE_R18_R22_SUMMARY.md>)）：8 px 與 0.08 px 是 `stepguard` 較好，但決策主軸是 0.8 px，在那裡兩個 R22 候選都沒超越 R18。這次外部比較同時解了 `stepguard` 對 `hold` 的平手：外部是 `hold` 較好，但因為都沒超越 R18，這個結果沒有實際效力。
3. **這次脫節決定了之後的驗收方式**：內部分數只當篩選，外部 GMF 才是最後關卡。

## 拿資料與重做

可重做程度：**partial**，依賴共用的舊工具。選定種子 `selected/current_round22_pairmix_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[事後檢討](<ROUND22_POSTMORTEM.md>)、[pairmix 決策](<selected/reports/ROUND22_PAIRMIX_HYBRID_DECISION_20260315_230456.md>)、[pairmix 摘要](<selected/reports/ROUND22_PAIRMIX_HYBRID_SUMMARY_20260315_230314.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round22.md>)。
