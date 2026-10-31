# 交付包

拿出去就能用的包。每個包裡有自己的程式、需要的來源、說明，以及當時怎麼核對的紀錄。包的名字比較新，不代表它取代了正式基準；早期的論文交接包，照它當時的日期去讀。

這一層按用途分成五類（2026-10-28 整理時分好，各包內容沒有改）：

- [Company_Packages](Company_Packages/README.md)：給合作廠商的部署包，有 COMBO、R39R40、R26，以及兩個 MOSR 的 ONNX 包。
- [Thesis_Handoffs](Thesis_Handoffs/README.md)：R128 到 R137 交給論文改寫用的資料包。
- [Standalone_Models](Standalone_Models/README.md)：不需要整個專案、自己就能跑的模型包，有 V42、R61、R129、R134、R137、R152。
- [Data_Regenerators](Data_Regenerators/README.md)：重新產生訓練資料的程式包。
- [Validations](Validations/README.md)：交付包當時的核對紀錄。

| 我要… | 打開 |
|---|---|
| 重新產生 R61 v16 的完整訓練資料 | [包的說明](Data_Regenerators/R61_TrainingData_Regenerator_20261004/README_TW.md)。3,400 組歷史來源和幾何要先取回，其餘 16,896 組由程式生成 |
| 單獨使用論文版 R152，或生成它的 TIFF 資料 | [影像檔版](Standalone_Models/R152_Standalone_ImageFiles_20261004/README.md)、[原本的獨立包](Standalone_Models/R152_Standalone_20261004/README.md) |
| 部署 R61 或其他 ONNX 模型 | [部署模型怎麼取得](../docs/reproducibility/ASSET_GUIDE.md)。R61 用原本那個 15 MB 的包就好，不用下載 3 GB 的舊可攜版 ZIP |
| 找舊的 COMBO、R39R40 部署方式 | [廠商部署包](Company_Packages/README.md) |
| 找 R128 到 R137 的論文交接或原稿 | 各日期的包都留著當作歷史；現在的論文入口是 [R153 交接](../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md) |
| 找論文原稿、原始圖檔和版本取捨 | [精選的歷史交付](../docs/reproducibility/project_completion/curated/draft_cleanup_20261022/README.md) |

大的模型檔和固定來源放在各版本的 Releases 附件裡，這個資料夾不是每個包的完整鏡像。照包裡寫的版本和用途去取回。另外注意：別的專案裡也有叫 R152 的東西，跟這裡的 R152 無關，不要混用。
