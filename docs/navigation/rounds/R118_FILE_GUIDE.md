# main/R118_PhysicalCoordinateRepairScratch：檔案怎麼找

[本輪研究卡](<../../reproducibility/experiments/main__R118_PhysicalCoordinateRepairScratch.md>) · [全部研究分區](<../../reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../reproducibility/STATUS.md>)

**研究問題：修正符號方向、連續寬度與真實二維定位。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R118 next-design execution handoff](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/reports/R118_EXECUTION_HANDOFF.md>)
- [可直接交給接手模型的執行指令](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/reports/R118_EXECUTOR_PROMPT.md>)
- [R118 next-work handoff preparation results](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/reports/R118_HANDOFF_PREPARATION_RESULTS.md>)
- [Next-design implementation cards](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/reports/R118_IMPLEMENTATION_TASKS.md>)
- [R118 next-work measurement contract](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/reports/R118_MEASUREMENT_CONTRACT.md>)
- [Execution and recovery runbook](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/reports/R118_OPERATION_RUNBOOK.md>)

其餘原報告見[本輪完整研究卡](<../../reproducibility/experiments/main__R118_PhysicalCoordinateRepairScratch.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [AGENTS.md](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/AGENTS.md>) | 1檔 | R118 handoff entry |
| [config/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/config>) | 1檔 | 實驗設定、條件與來源鎖定 |
| [data/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/data>) | 4檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [Infer.py](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/Infer.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [inference/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/MANIFEST.md>) | 1檔 | R118 package manifest |
| [model/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/model>) | 2檔 | 本輪模型程式 |
| [NEXT_STEPS.md](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/NEXT_STEPS.md>) | 1檔 | Next execution entry |
| [README.md](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/README.md>) | 1檔 | R118 physical-coordinate repair |
| [reports/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/reports>) | 7檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/results>) | 3檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/scripts>) | 6檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/tests>) | 2檔 | 原檢查程式；不是研究結果本身 |
| [Train.py](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/Train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/training>) | 3檔 | 訓練程式與配套 |
| [validation/](<../../../Experiments/R118_PhysicalCoordinateRepairScratch/validation>) | 7檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

5000／512固定幾何、新8倍觀測及封存確認狀態。

[按用途取得原件](<../../reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
