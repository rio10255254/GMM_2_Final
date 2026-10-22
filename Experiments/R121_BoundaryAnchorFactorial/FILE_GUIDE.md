# main/R121_BoundaryAnchorFactorial：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R121_BoundaryAnchorFactorial.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：將亮暗擴充與局部位置要求做四組對照。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R121 四組短測的方法與修訂紀錄](<reports/R121_METHODOLOGY.md>)
- [R121：SEM 與光學邊界參考核對](<reports/R121_REFERENCE_AUDIT.md>)
- [R121 四組修正短測：未找到可採用的新模型](<reports/R121_RESULTS.md>)
- [實驗索引 / Experiment Index](<reports/project_context_before/Experiments__INDEX.md>)
- [PROJECT STATE / 專案狀態](<reports/project_context_before/PROJECT_STATE.md>)
- [實驗重建影像 Gallery / Experiment Recon Gallery](<reports/project_context_before/RECON_GALLERY.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 10檔 | 實驗設定、條件與來源鎖定 |
| [Infer.py](<Infer.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R121 evidence and execution scope |
| [model/](<model>) | 2檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R121 Boundary Anchor Factorial |
| [reports/](<reports>) | 11檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 4檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 14檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 2檔 | 原檢查程式；不是研究結果本身 |
| [Train.py](<Train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training/](<training>) | 8檔 | 訓練程式與配套 |
| [validation/](<validation>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

R118／R120精確來源、兩套SEM參照及八組設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
