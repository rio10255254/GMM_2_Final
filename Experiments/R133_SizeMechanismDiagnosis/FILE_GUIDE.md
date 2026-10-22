# main/R133_SizeMechanismDiagnosis：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R133_SizeMechanismDiagnosis.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：拆解尺寸偏大來自光學、學習還是最後輸出。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R133 固定設計](<reports/R133_METHODOLOGY.md>)
- [R133 底層修正方案：先對齊物理問題，再修模型接口](<reports/R133_REPAIR_DESIGN.md>)
- [R133：為何尺寸仍不準，以及底層修正方向](<reports/R133_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 2檔 | 實驗設定、條件與來源鎖定 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R133 Manifest |
| [README.md](<README.md>) | 1檔 | R133 尺寸偏差底層診斷 |
| [reports/](<reports>) | 6檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 7檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 8檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

64控制、128生成來源、固定R129及972 SEM讀值。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
