# main/R102_UniversalDetailScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R102_UniversalDetailScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：以局部主幹同時恢復細節與位置。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R102_UniversalDetailScratch 研究保存清單](<MANIFEST.md>)
- [R102 Universal Detail Scratch](<README.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analysis/](<analysis>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [config/](<config>) | 1檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 2檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [evaluation/](<evaluation>) | 1檔 | 量測介面、固定參照、設定或比較內容 |
| [inference/](<inference>) | 2檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R102_UniversalDetailScratch 研究保存清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [Open_Training_Monitor.cmd](<Open_Training_Monitor.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [README.md](<README.md>) | 1檔 | R102 Universal Detail Scratch |
| [runs/](<runs>) | 2檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts>) | 2檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [Start_R102_Training.cmd](<Start_R102_Training.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 4檔 | 訓練程式與配套 |

## 必要來源與取得界線

固定5000觀測、實際歷程與塌縮診斷。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
