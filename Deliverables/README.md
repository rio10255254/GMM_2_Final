# 可獨立使用的交付與資料生成包

各子包保存自己的程式、必要來源、說明及原核對範圍。名稱較新不代表已取代正式基準；早期論文交接按原日期讀。

這一層按用途分五類（2026-10-28 重整時分好，各包內容沒有改）：

- [Company_Packages](Company_Packages/README.md)：給合作廠商的部署包，含 COMBO、R39R40、R26 與兩個 MOSR ONNX。
- [Thesis_Handoffs](Thesis_Handoffs/README.md)：R128 到 R137 交給論文改寫的資料包。
- [Standalone_Models](Standalone_Models/README.md)：可以獨立使用的模型包，含 V42、R61、R129、R134、R137、R152。
- [Data_Regenerators](Data_Regenerators/README.md)：重新產生訓練資料的程式包。
- [Validations](Validations/README.md)：交付包當時的核對紀錄。

| 需要什麼 | 入口 |
|---|---|
| R61 v16完整訓練資料重新生成 | [原包說明](Data_Regenerators/R61_TrainingData_Regenerator_20261004/README_TW.md)；先取回3,400組歷史來源／幾何，其餘16,896組生成 |
| R152論文版獨立使用、TIFF資料生成 | [影像檔包](Standalone_Models/R152_Standalone_ImageFiles_20261004/README.md)、[原獨立包](Standalone_Models/R152_Standalone_20261004/README.md) |
| R61及其他ONNX部署 | [部署模型取得指南](../docs/reproducibility/ASSET_GUIDE.md)；R61原15MB包沿原介面，不必下載3GB舊便攜ZIP |
| 舊COMBO／R39R40部署相容入口 | [舊交付區](Company_Packages/README.md) |
| R128至R137的論文交接／原稿 | 原日期子包保留歷史；[目前R153交接](../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)才是今日入口 |
| 原稿、原製圖與版本取捨 | [精選歷史交付](../docs/reproducibility/project_completion/curated/draft_cleanup_20261022/README.md) |

大模型／固定來源在對應版本附件，這個資料夾不是每個包的全部資料鏡像。依包內固定版本及用途取回，不將另一個專案同名R152的資料混入。
