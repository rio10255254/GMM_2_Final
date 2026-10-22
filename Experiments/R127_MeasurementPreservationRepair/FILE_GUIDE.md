# main/R127_MeasurementPreservationRepair：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R127_MeasurementPreservationRepair.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：修正SEM比例／取邊、位移有效性與條件原樣保留。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [要把影像一致性進一步驗成實際準確，需要補什麼](<reports/R127_ACQUISITION_PLAN.md>)
- [R127 execution and retained failures](<reports/R127_EXECUTION_NOTES.md>)
- [R127 methodology and completion criteria](<reports/R127_METHODOLOGY.md>)
- [R127 — 三項修正已實跑；量測跳值已釐清，物理尺寸仍需獨立對照](<reports/R127_RESULTS.md>)
- [R127 reusable image-pair measurement](<reports/R127_USAGE.md>)
- [實驗索引 / Experiment Index](<reports/project_context_before/INDEX.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R127_MeasurementPreservationRepair.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 10檔 | 實驗設定、條件與來源鎖定 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R127 identity |
| [README.md](<README.md>) | 1檔 | R127 — Measurement and preservation repair |
| [reports/](<reports>) | 11檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 1檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 26檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

來源SEM、72讀法測試、48完整輸出與24模型位移。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
