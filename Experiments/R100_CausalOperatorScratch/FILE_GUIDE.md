# main/R100_CausalOperatorScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R100_CausalOperatorScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：在原有形狀上加入輪廓外程序紋理。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R100_CausalOperatorScratch 研究保存清單](<MANIFEST.md>)
- [R100](<README.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analysis/](<analysis>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [config/](<config>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 1檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [inference/](<inference>) | 2檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R100_CausalOperatorScratch 研究保存清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R100 |
| [reports/](<reports>) | 1檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 33檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 8檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [Start_R100_Training.cmd](<Start_R100_Training.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 3檔 | 訓練程式與配套 |

## 必要來源與取得界線

1250場景／5000觀測、線上紋理配方與實際40輪設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
