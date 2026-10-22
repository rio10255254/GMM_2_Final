# main/R93_RecoverableDetailSeparatedScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R93_RecoverableDetailSeparatedScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：拆開可恢復細節及清楚輸入保護。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R93 原始來源、停止結果與 GitHub 重做審查（2026-10-20）](<reports/R93_AUDIT.md>)
- [R93 Manifest](<MANIFEST.md>)
- [Round 93 — Recoverable Detail Separated Scratch](<README.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [.gitignore](<.gitignore>) | 1檔 | 原配套檔案 |
| [config/](<config/README.md>) | 6檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data/README.md>) | 4檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R93 Manifest |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | Round 93 — Recoverable Detail Separated Scratch |
| [reports/](<reports/README.md>) | 9檔 | 原報告、計畫、審查與各階段結論 |
| [scripts/](<scripts/README.md>) | 11檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 2檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 1檔 | 訓練程式與配套 |

## 必要來源與取得界線

精確5000觀測生成／修復記錄、來源清單與各下游約定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
