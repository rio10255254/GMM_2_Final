# main/R124_RealFirstPrototype：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R124_RealFirstPrototype.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：實作四步二維重建及可保存重載的原型。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R124 implementation contract](<reports/R124_IMPLEMENTATION.md>)
- [R124 — 模型原型已實作並實際跑通](<reports/R124_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 3檔 | 實驗設定、條件與來源鎖定 |
| [inference/](<inference>) | 3檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R124 identity and scope |
| [model/](<model>) | 5檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R124 — 可執行的下一代模型原型 |
| [reports/](<reports>) | 2檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 5檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 5檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 3檔 | 原檢查程式；不是研究結果本身 |

## 必要來源與取得界線

原型程式、兩個診斷成像設定、原始初始化與測試輸入。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
