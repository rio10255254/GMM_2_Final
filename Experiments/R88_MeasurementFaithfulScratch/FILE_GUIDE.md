# main/R88_MeasurementFaithfulScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R88_MeasurementFaithfulScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：修復R87紋理與邊界並加入實際量測約束。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R88 訓練停止紀錄](<reports/R88_ABORTED_AT_E87.md>)
- [R88 驗收門檻](<reports/R88_ACCEPTANCE_GATES.md>)
- [R88 完整實驗設計](<reports/R88_EXPERIMENT_DESIGN.md>)
- [R88 原始研究與設計對照](<reports/R88_LITERATURE_SYNTHESIS.md>)
- [R88 歷代問題清單](<reports/R88_PROBLEM_LEDGER.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [.gitignore](<.gitignore>) | 1檔 | 原配套檔案 |
| [archive/](<archive>) | 2檔 | 舊內容及當次封存紀錄 |
| [config/](<config>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [inference/](<inference>) | 2檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R88 Manifest |
| [model/](<model>) | 2檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R88：量測忠實的獨立從零訓練 |
| [reports/](<reports>) | 5檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 3檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [runs/](<runs>) | 1檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts>) | 12檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 2檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 2檔 | 訓練程式與配套 |
| [weights/](<weights>) | 1檔 | 模型檔或取得說明；最佳、最後及短測版本需分清 |

## 必要來源與取得界線

獨立生成配方、實際87輪歷程、被保留模型與封存確認狀態。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
