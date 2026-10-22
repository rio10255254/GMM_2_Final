# main/R89_MeasurementNativeScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R89_MeasurementNativeScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：移除輸出信心閘並直接學習有界重建。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R89 Lock Timeline](<reports/R89_LOCK_TIMELINE.md>)
- [R89 Preflight Summary](<reports/R89_PREFLIGHT_SUMMARY.md>)
- [R89 第 100 輪最終驗證](<reports/final_validation/R89_FINAL_VALIDATION_TW.md>)
- [R89 各階段 SEM 輪廓與 5x/20x 檢查](<reports/final_validation/stage_weight_analysis/R89_STAGE_WEIGHT_FINDINGS_TW.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 5檔 | 實驗設定、條件與來源鎖定 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R89 File Manifest |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R89 Measurement-Native Scratch |
| [reports/](<reports>) | 4檔 | 原報告、計畫、審查與各階段結論 |
| [runs/](<runs>) | 1檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts>) | 14檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 2檔 | 原檢查程式；不是研究結果本身 |
| [training/](<training>) | 1檔 | 訓練程式與配套 |

## 必要來源與取得界線

本輪原生成器、匿名統計、固定初值與完整結果。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
