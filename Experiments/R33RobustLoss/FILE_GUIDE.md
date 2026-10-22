# main/R33RobustLoss：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R33RobustLoss.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：減少極端像素牽引是否改善位移穩定。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [GMF step_std 計算方法論](<reports/GMF_STEP_STD_METHODOLOGY.md>)
- [Internal vs External Step_std 偏差分析](<reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md>)
- [推理量化修復分析](<reports/QUANTIZATION_FIX_ANALYSIS.md>)
- [R33 Robust Loss — Experiment Summary](<reports/R33_EXPERIMENT_SUMMARY.md>)
- [R33-R38v2 完整實驗系列報告](<reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md>)
- [R33 robust_p90 Results (2026-04-05)](<reports/r33_robust_p90_results.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R33 — Robust Loss (Winsorize Spatial Loss) |
| [README.md](<README.md>) | 1檔 | Round 33 — Residual-Guided Robust Loss |
| [reports/](<reports>) | 8檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 150檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 2檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

R30模型、當時PSF及環形／序列來源，固定GMF讀法。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
