# main/R84_R79TileStableRootRepair：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R84_R79TileStableRootRepair.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：移除R79對看到範圍的依賴。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R79 根治與完整檢測結案](<reports/R79_ROOT_REPAIR_CLOSEOUT.md>)
- [R84 最終判決](<reports/R84_FINAL_VERDICT.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [.gitignore](<.gitignore>) | 1檔 | 原配套檔案 |
| [config/](<config>) | 2檔 | 實驗設定、條件與來源鎖定 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R84_R79TileStableRootRepair 研究保存清單 |
| [model/](<model>) | 2檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R84：R79 切片穩定根治 |
| [reports/](<reports>) | 2檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 8檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 12檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 1檔 | 訓練程式與配套 |

## 必要來源與取得界線

原R79與三種修復設定、固定形狀／SEM／位移資料。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
