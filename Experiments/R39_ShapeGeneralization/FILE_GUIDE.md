# main/R39_ShapeGeneralization：檔案怎麼找

[共用固定來源與模型關係](../../docs/reproducibility/round_source_reviews/BASELINE_20261023.md) · [原結果直接閱讀](results/SOURCE_RESULTS_GUIDE.md)

[本輪研究卡](<../../docs/reproducibility/experiments/main__R39_ShapeGeneralization.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：保留環形能力並擴大非環形重建。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R39 a030 在多樣顯微圖形上的詳細評估](<reports/R39_A030_MICROSCOPY_EVALUATION.md>)
- [R39 外部 GMF 比較 — `r39_combo_strong_avg_a030`](<reports/R39_EXTERNAL_COMPARE.md>)
- [R39 結果 — 多形狀泛化](<reports/R39_RESULTS.md>)
- [R39R40 a025 ONNX 交付包內容審核](<results/a030_x_a043_sweep/reports/R39R40_A025_ONNX_PACKAGE_CONTENT_AUDIT_20260513.md>)
- [R39R40 a025 全面能力評估](<results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md>)
- [R40 External GMF Compare - `r39r40_avg_a025`](<results/a030_x_a043_sweep/reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R39_ShapeGeneralization.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R39 Shape Generalization Manifest |
| [README.md](<README.md>) | 1檔 | R39 — 多形狀泛化 |
| [reports/](<reports>) | 3檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 55檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 23檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 4檔 | 原檢查程式；不是研究結果本身 |

## 必要來源與取得界線

COMBO、R39與R40端點、平均比例、形狀生成及固定分組。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
