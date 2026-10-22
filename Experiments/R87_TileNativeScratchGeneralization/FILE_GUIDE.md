# main/R87_TileNativeScratchGeneralization：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R87_TileNativeScratchGeneralization.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：純局部模型從零學習重建及切片一致性。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R87 Results](<reports/R87_RESULTS.md>)
- [下一輪真實紋理保留方案](<reports/R88_TEXTURE_PRESERVING_PLAN.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [.gitignore](<.gitignore>) | 1檔 | 原配套檔案 |
| [ARCHIVE_POINTER_R87_20260926.md](<ARCHIVE_POINTER_R87_20260926.md>) | 1檔 | R87 完整歷史封存入口 |
| [config/](<config>) | 1檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 5檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [inference/](<inference>) | 2檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R87 Manifest |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | Round 87 — Tile-Native Scratch Generalization |
| [reports/](<reports>) | 3檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 1檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 6檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 2檔 | 訓練程式與配套 |
| [weights/](<weights>) | 1檔 | 模型檔或取得說明；最佳、最後及短測版本需分清 |

## 必要來源與取得界線

1280場景原生成器、實際配方、固定模型、R73／R74及H完整封存。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
