# main/R135_UnifiedModelComparison：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R135_UnifiedModelComparison.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：統一模型、保存精度與SEM／位移量法。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R61 v16訓練資料與評估答案關係審查](<reports/R135_R61_TRAINING_AUDIT.md>)
- [R135：包含舊V42的統一比較](<reports/R135_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 3檔 | 實驗設定、條件與來源鎖定 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R135 manifest |
| [README.md](<README.md>) | 1檔 | R135 六個固定模型的統一量測比較 |
| [reports/](<reports>) | 4檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 106檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 22檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [STATUS_R135.cmd](<STATUS_R135.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [validation/](<validation>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

七組固定方法、共同201原圖、SEM映射與來源審查。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
