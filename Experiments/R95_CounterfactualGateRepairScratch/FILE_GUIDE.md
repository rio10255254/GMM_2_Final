# main/R95_CounterfactualGateRepairScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R95_CounterfactualGateRepairScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：修復R94修正閘與訓練動力問題。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R95 方法、實際完成與 GitHub 保存審查](<reports/R95_AUDIT.md>)
- [R95 保存與來源清單](<MANIFEST.md>)
- [R95：修復控制與學習動力](<README.md>)
- [R95 data policy](<data/README.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [archive/](<archive>) | 8檔 | 舊內容及當次封存紀錄 |
| [config/](<config>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 1檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [logs/](<logs>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R95 保存與來源清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [Open_Training_Monitor.cmd](<Open_Training_Monitor.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [README.md](<README.md>) | 1檔 | R95：修復控制與學習動力 |
| [reports/](<reports>) | 1檔 | 原報告、計畫、審查與各階段結論 |
| [runs/](<runs>) | 7檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts>) | 26檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 2檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 5檔 | 訓練程式與配套 |

## 必要來源與取得界線

R93資料、固定反事實設定及本輪完整48輪歷程。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
