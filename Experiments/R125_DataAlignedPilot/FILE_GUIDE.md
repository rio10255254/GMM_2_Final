# main/R125_DataAlignedPilot：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R125_DataAlignedPilot.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：先對齊資料形成與模型，再實際小訓練。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R125 資料與模型契約核對](<reports/R125_DATA_FIT.md>)
- [R125 data-to-model execution contract](<reports/R125_METHODOLOGY.md>)
- [R125 — 下一步已實跑；資料只部分適合，尚不能擴大訓練](<reports/R125_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 5檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 2檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R125 identity |
| [prototype/](<prototype>) | 3檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [README.md](<README.md>) | 1檔 | R125 — 資料相容性修正與第一輪實際小試跑 |
| [reports/](<reports>) | 5檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 6檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [runs/](<runs>) | 1檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts>) | 13檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 7檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 6檔 | 訓練程式與配套 |

## 必要來源與取得界線

兩版生成、六組共同初值、12次實拍結果。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
