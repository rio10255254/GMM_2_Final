# main/R128_SourceOnlyFullTraining：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R128_SourceOnlyFullTraining.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：用獨立生成來源做四個完整研究訓練。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [最終應用範圍：可控制的正常拍攝條件](<reports/R128_APPLICATION_SCOPE.md>)
- [R128 與近期模型：LSC、完整輪廓與圓度的同條件盤點](<reports/R128_COMPETITIVE_REVIEW.md>)
- [R128 執行與修正紀錄](<reports/R128_EXECUTION_NOTES.md>)
- [R128 final execution and result audit](<reports/R128_FINAL_AUDIT.md>)
- [完整Contour是否真的更貼近SEM](<reports/R128_FULL_CONTOUR_SEM.md>)
- [R128 與 R61、近期模型：完整同條件位移比較](<reports/R128_LSC_R61_COMPARISON.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R128_SourceOnlyFullTraining.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analysis/](<analysis>) | 72檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [config/](<config>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 2檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [evaluation/](<evaluation>) | 3檔 | 量測介面、固定參照、設定或比較內容 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R128 run identity |
| [model/](<model>) | 3檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R128 — Source-only full training |
| [recovery/](<recovery>) | 18檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [reports/](<reports>) | 39檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 126檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 10檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [training/](<training>) | 4檔 | 訓練程式與配套 |
| [trial/](<trial>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

768場景原生成鏈、四組初值／設定及各個固定比較模型。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
