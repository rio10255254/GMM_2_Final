# main/R94_EvidenceConditionalScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R94_EvidenceConditionalScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：按成像順序分工並直接教何時需要修正。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R94 方法、實際完成與 GitHub 保存審查](<reports/R94_AUDIT.md>)
- [R94 保存與來源清單](<MANIFEST.md>)
- [R94：按成像順序分工](<README.md>)
- [R94 data policy](<data/README.md>)
- [R94 weights](<weights/README.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [archive/](<archive>) | 20檔 | 舊內容及當次封存紀錄 |
| [config/](<config>) | 3檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 1檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R94 保存與來源清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R94：按成像順序分工 |
| [reports/](<reports>) | 1檔 | 原報告、計畫、審查與各階段結論 |
| [runs/](<runs>) | 15檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts>) | 14檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 5檔 | 訓練程式與配套 |
| [weights/](<weights>) | 1檔 | 模型檔或取得說明；最佳、最後及短測版本需分清 |

## 必要來源與取得界線

R93鎖定資料、初值與第8輪錯誤／梯度診斷。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
