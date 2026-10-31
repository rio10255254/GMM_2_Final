# 讀懂與重做這個研究

[專案首頁](../../README.md) · [目前保存狀態](STATUS.md) · [完整資料夾地圖](../navigation/PROJECT_MAP.md)

建議先讀懂研究在問什麼、怎麼做、結果如何，真的要重做某一段時，再去取需要的資料。這裡是導讀，不是要你把所有附件都下載下來的清單。

## 照你的目的走

| 我想… | 這樣走 |
|---|---|
| 第一次讀這個研究 | [入門](GETTING_STARTED.md) → [研究沿革](lineage/README.md) → [目前的論文交接](../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md) |
| 找某一輪或 Lab 的某條支線 | [分階段的實驗目錄](EXPERIMENTS.md) → 那一輪的閱讀卡 → 原報告、設定和完整結果 |
| 看失敗怎麼帶出下一輪 | [沿革裡的研究轉折](lineage/README.md)、[失敗的原始數表](project_completion/curated/FAILURE_LINEAGE_READING.md) |
| 找參考文獻和方法出處 | [文獻、官方程式和本專案怎麼用](LITERATURE_GUIDE.md) |
| 找原始照片、量測或模型 | [原始資料](../../Shared_Sources/README.md) → [按用途取得](ASSET_GUIDE.md)；模型另外查[模型指南](MODEL_GUIDE.md) |
| 重新生成訓練資料 | [生成方法與需要的來源](GENERATION_GUIDE.md)。可以重新生成的影像，和換不回來的原件分開處理 |
| 確認東西保存到什麼程度 | [現在的狀態](STATUS.md) → [缺件和影響](KNOWN_GAPS.md)；要查以前交付過什麼才看[保存歷史](project_completion/README.md) |

## 各條研究線的深入閱讀

| 研究線 | 讀這些 |
|---|---|
| 早期調參與選模 | [早期沿革](lineage/EARLY_ROUNDS.md)、[原始 JSON 對照](lineage/EARLY_REPORTS.md)、[三種位移尺度與公式](legacy_multiscale/README.md) |
| R33 到 COMBO | [完整系列原報告](../../Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md)、[只在舊分支的輪次](lineage/HISTORICAL_BRANCHES.md) |
| 實驗室顯微鏡（LabSystem） | [校正、資料和 V41／V42 的沿革](lineage/LAB_SYSTEM.md)、[原始比較與小型重算](lab_comparisons/README.md) |
| 從零訓練與資料怎麼做出來 | [R89 到 R93](scratch_lineage/README.md)、[R93 共用的來源](r93_shared/README.md)、[R94／95／97／98](four_rounds/README.md) |
| 原始量測與失敗 | [R128／R129／R135 完整原表](project_completion/curated/IMPORTANT_TABLES_20261022.md)、[R100／103／104 的不利結果](project_completion/curated/FAILURE_LINEAGE_READING.md) |
| 光學來源 | [PSF 原拍](../../Shared_Sources/PSF_Camera_Acquisitions/README.md)、[光學資料的保存審查](../../PSF_Fitting/docs/PSF_GITHUB_PRESERVATION_AUDIT_20261021.md)、[頻譜來源](optical_calibration/SPECTRA.md) |

研究結論以各輪原本的正式報告為準，這裡只負責把它們串起來，不另外下判斷。讀的時候注意三件事：同一個 R 編號可能屬於不同系統；stage 是資料的類型，不是第幾次訓練；V 是版本號。詳細見[編號與沿革](lineage/README.md)。
