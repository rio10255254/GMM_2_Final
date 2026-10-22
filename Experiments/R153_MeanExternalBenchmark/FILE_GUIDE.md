# main/R153_MeanExternalBenchmark：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R153_MeanExternalBenchmark.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：用九顆平均位移與外部架構完成論文比較。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [已完成模型的新重建效率比較](<reports/AVAILABLE_MODELS_EFFICIENCY.md>)
- [已完成模型之完整實拍驗證與效率比較](<reports/AVAILABLE_MODELS_PROGRESS.md>)
- [已完成模型之完整實拍驗證與效率比較](<reports/AVAILABLE_MODELS_REAL_RESULTS.md>)
- [已完成方法之論文比較交接](<reports/AVAILABLE_MODELS_STAGE_COMPLETE/REPORT.md>)
- [已完成方法之論文比較交接](<reports/AVAILABLE_MODELS_STAGE_PROGRESS/REPORT.md>)
- [外部模型比較結果與完成狀態](<reports/BENCHMARK_RESULTS.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R153_MeanExternalBenchmark.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [benchmark_core.py](<benchmark_core.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [benchmark_models.py](<benchmark_models.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [config/](<config/README.md>) | 14檔 | 實驗設定、條件與來源鎖定 |
| [evaluation/](<evaluation/README.md>) | 3檔 | 量測介面、固定參照、設定或比較內容 |
| [inference_methods.py](<inference_methods.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | Benchmark execution record |
| [normal_data.py](<normal_data.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [normal_protocol.py](<normal_protocol.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [normal_training.py](<normal_training.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [README.md](<README.md>) | 1檔 | MOSR mean aggregation and external benchmark |
| [reports/](<reports/README.md>) | 125檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results/CONTENTS.md>) | 2檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [runs/](<runs/README.md>) | 10檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts/README.md>) | 28檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [short_budget.py](<short_budget.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [study.py](<study.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [vendor/](<vendor>) | 107檔 | 第三方原碼與授權，保持上游身分 |

## 必要來源與取得界線

共同R152生成資料、七個官方來源／實際改動／模型、完整圓心／邊界／PI／效率讀值。

目前先看[最終十方法交接](<reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md>)；七方法、九方法和mean-only包保留原階段。下方連結不授權重新訓練。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
