# 論文證據

本區保存論文主張的來源、跨模型比較及較早草稿／補測。原本也在這裡的 LabSystem，2026-10-28 重整時移到根目錄 [LabSystem_MOSR](../LabSystem_MOSR/README.md)，內容沒有改。**目前論文採R152／RAW，最新交接在[R153原完整報告](../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)**；不能用本區舊版v2章節設想取代目前論文。

## 從用途找

| 目的 | 入口 |
|---|---|
| 現在採用什麼、完整十方法結果與限制 | [R153論文交接](../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)、[目前狀態](../PROJECT_STATE.md) |
| Lab校正、訓練資料、R39／40至R62及V41／V42 | [Lab研究全線](../docs/reproducibility/lineage/LAB_SYSTEM.md)、[Lab原工作區](../LabSystem_MOSR/README.md) |
| 模型設計、效果與未採用原因 | [2026-09-26原回顧](Research_Design_Effect_Review_20260926/README.md)，按原日期閱讀；[全研究沿革](../docs/reproducibility/lineage/README.md)含後續主R至153 |
| 完整原數表、SEM、位移和重拍 | 先由[逐輪閱讀](../docs/reproducibility/EXPERIMENTS.md)找所屬報告；[來源與圖冊](../docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)分清原拍、答案及模型輸出 |
| 原論文、修訂與可編輯圖 | [精選原稿及製圖來源](../docs/reproducibility/project_completion/curated/draft_cleanup_20261022/README.md)、[較早編輯歷史](../docs/reproducibility/project_completion/EDITOR_HISTORY.md) |

## 本區的原結構

原本在本區的`LabSystem_MOSR`（現在在根目錄）是具有自己校正、資料和模型歷史的工作區；Lab R39不等於主R39，V42不等於主R42。其他`Experiments`、日期型分析及章節證據，按其原報告與時間閱讀。

`visual_vs_metric_decoupling`、`error_type_transformation`、`method_ablations`等名稱來自早期章節／機制設想。資料夾存在不代表所有因果主張已驗證，完成範圍回各自報告，不能把設想寫成已完成證明。

本區服務論文證據，`Analyses/AnalysisLab`服務跨版本分析工具，主`Experiments`保留主R輪次的正式報告。原相機、SEM答案與訓練來源依賴須連同數據一起讀；重拍穩定不等於絕對準確，同樣本答案也不自動成為獨立驗證。

[本次整理前的原首頁與章節敘事](https://github.com/rio10255254/GMM_2_Final/blob/1b1cbdf3804df53f0e3c853b8dcf57e7471c6520/Thesis_MOSR_Evidence/README.md)保留原文，原稿、圖、研究程式和結果沒有因首頁整理而搬動或改寫。
