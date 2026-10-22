# main/R98_AggressiveTextureScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R98_AggressiveTextureScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：增加可見多尺度紋理的恢復強度。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R98 方法、實際完成與 GitHub 保存審查](<reports/R98_AUDIT.md>)
- [R98 METHODOLOGY](<reports/R98_METHODOLOGY.md>)
- [R98 RESULTS](<reports/R98_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 3檔 | 實驗設定、條件與來源鎖定 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [logs_preflight_console.txt](<logs_preflight_console.txt>) | 1檔 | 原說明／報告／歷史紀錄 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R98 保存與來源清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [Open_Training_Monitor.cmd](<Open_Training_Monitor.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [README.md](<README.md>) | 1檔 | R98：加強原圖可見紋理 |
| [reports/](<reports>) | 3檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 1檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 7檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 6檔 | 訓練程式與配套 |

## 必要來源與取得界線

共享R93／R97來源、六頻帶及固定48輪設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
