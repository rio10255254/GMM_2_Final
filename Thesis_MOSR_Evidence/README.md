# 論文證據

這裡放論文裡各項說法的來源、跨模型的比較，以及較早的草稿和補做的測試。

**論文現在用的是 R152（MOSR）對照 RAW，最新的交接在 [R153 完整報告](../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)。** 這個資料夾裡有一份較早的 v2 章節構想，那是當時的規劃，不是現在的論文。

原本放在這裡的實驗室顯微鏡研究線，2026-10-28 移到最上層的 [LabSystem_MOSR](../LabSystem_MOSR/README.md)，內容沒有改。

## 照用途找

| 我想找… | 打開 |
|---|---|
| 現在用哪個模型、十種方法的完整結果和限制 | [R153 論文交接](../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)、[目前狀態](../PROJECT_STATE.md) |
| Lab 的校正、訓練資料、R39／40 到 R62、V41／V42 | [Lab 研究全線](../docs/reproducibility/lineage/LAB_SYSTEM.md)、[Lab 的資料夾](../LabSystem_MOSR/README.md) |
| 模型怎麼設計、效果如何、為什麼沒採用 | [2026-09-26 的回顧](Research_Design_Effect_Review_20260926/README.md)（照當時的日期讀）；之後一直到 R153 的發展看[研究沿革](../docs/reproducibility/lineage/README.md) |
| 完整的原始數表、SEM、位移和重拍 | 先從[逐輪閱讀](../docs/reproducibility/EXPERIMENTS.md)找到所屬的報告；[每批照片的來源與用途](../docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)分清楚哪些是原拍、哪些是參考答案、哪些是模型輸出 |
| 論文原稿、修訂版和可以編輯的圖 | [精選原稿與製圖來源](../docs/reproducibility/project_completion/curated/draft_cleanup_20261022/README.md)、[較早的編輯歷史](../docs/reproducibility/project_completion/EDITOR_HISTORY.md) |

## 讀這裡的東西要注意

- `visual_vs_metric_decoupling`、`error_type_transformation`、`method_ablations` 這些資料夾名稱，來自早期的章節構想。資料夾存在，不代表裡面的推論都驗證過了，實際做到哪裡要看各自的報告。
- 這裡放論文證據；跨版本的分析工具在 `Analyses/AnalysisLab`；主專案每一輪的正式報告在 `Experiments`。
- 讀數字時要連同它的來源一起看：用的是哪批原拍、有沒有用到 SEM 參考答案、訓練資料從哪來。重拍穩定不等於絕對準確；同一片樣品的答案，也不會自動變成獨立驗證。

[2026-10-22 整理前的首頁與章節敘事](https://github.com/rio10255254/GMM_2_Final/blob/1b1cbdf3804df53f0e3c853b8dcf57e7471c6520/Thesis_MOSR_Evidence/README.md)保留原文。整理說明文字時，原稿、圖、研究程式和結果都沒有搬動或改寫。
