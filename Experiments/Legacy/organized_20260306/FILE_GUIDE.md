# 2026-03-06 批次：R1 之前的基準版 step8_curve_sharp

[研究時間線](<../../../docs/research/TIMELINE.md>) · [早期輪次對照](<../../../docs/reproducibility/lineage/EARLY_ROUNDS.md>) · [下一個批次 3/07（R1）](<../organized_20260307/FILE_GUIDE.md>)

**一句話：** 專案最早期的自動調參批次。目標是讓模型對真實的 1 µm＝8 px 位移更敏感，供下游 GMF 使用；這一批加入了「已知步長的 GMF 代理驗證」（用一張固定監控影像合成已知 8 px 步長的序列）、新增曲邊與環形邊緣缺陷的資料階段，並跑了四個候選家族。最後採用 `step8_curve_sharp`，取代更早的 `annulus_focus_boundary`，成為之後 3/07 起所有測試的比較基準。這批之後就凍結。

| | |
|---|---|
| 結果 | **採用**（當時的基準版；3/07 起的新測試都拿它當比較基準，之後被後續輪次取代） |
| 時間 | 2026-03-06 |
| 實驗條件 | 程式資料：合成曲邊與環形資料（新增 stage 13、14）；內部用已知 8 px 步長的代理驗證 |
| 起點 | 當時的 GeoEdgeAlignSR 訓練程式 |

## 讀這些內容要知道的事

1. **四個候選家族**：`step8_curve_general`、`step8_curve_sharp`、`step8_general_balanced`、`step8_annulus_priority`。
2. **這一批做過大清理**：大量中間保存點、監控影像與未採用的 sweep 都刪了，只保留採用版的 `best_tradeoff.pth.tar`、歷史版的必要權重與必要紀錄；清理經過見三份清理報告。
3. 當時推論程式 `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py` 的預設權重就指向這個採用版。

## 拿資料與重做

採用 run 與權重在 `selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/`；位置查 `python Tools/cloud_locator.py where Experiments/Legacy/organized_20260306/selected`。

## 原始報告

[8 px 自動調參報告](<AUTO_TUNE_8PX_REPORT_20260306.md>)（採用依據）、[續跑報告](<AUTO_TUNE_CONTINUE_REPORT_20260306.md>)（舊採用版 `annulus_focus_boundary`）、清理報告（[3/06](<CLEANUP_REPORT_20260306.md>)、[3/06 v2](<CLEANUP_REPORT_20260306_v2.md>)、[3/07](<CLEANUP_REPORT_20260307.md>)）、[README](<README.md>)。保存紀錄見[本批次保存紀錄](<../../../docs/reproducibility/experiments/legacy__organized_20260306.md>)。
