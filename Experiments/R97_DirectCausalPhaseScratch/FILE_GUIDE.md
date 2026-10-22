# main/R97_DirectCausalPhaseScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R97_DirectCausalPhaseScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：直接預測每分支實際施加的修正。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R97 方法、實際完成與 GitHub 保存審查](<reports/R97_AUDIT.md>)
- [GPU incident record — 2026-08-13](<reports/gpu_incident_20260813.md>)
- [Same-run interruption recovery validation — 2026-08-13](<reports/recovery_validation_20260813.md>)
- [R97 root-cause matrix](<reports/root_cause_matrix.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R97 保存與來源清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [Open_Training_Monitor.cmd](<Open_Training_Monitor.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [README.md](<README.md>) | 1檔 | R97：直接修正與週期位置辨識 |
| [reports/](<reports>) | 4檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 4檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 15檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 6檔 | 訓練程式與配套 |

## 必要來源與取得界線

R93資料、線上程序週期樣本、48輪設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
