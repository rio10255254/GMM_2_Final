# main/R38v2SeqFixed：檔案怎麼找

[共用固定來源與模型關係](../../docs/reproducibility/round_source_reviews/BASELINE_20261023.md) · [原結果直接閱讀](results/SOURCE_RESULTS_GUIDE.md)

[本輪研究卡](<../../docs/reproducibility/experiments/main__R38v2SeqFixed.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：只保留有足夠訊號的序列訓練並結合R33。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [COMBO: Winsorize p95 + Seq 8px Gate + Warmup — Results](<reports/COMBO_RESULTS.md>)
- [R38v2 資料流審計](<reports/DATA_FLOW_AUDIT.md>)
- [R38v2 Sequence Consistency Training (Fixed) Results](<reports/R38v2_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R38v2 — Sequence Consistency Training (Fixed) |
| [README.md](<README.md>) | 1檔 | Round 38v2 — Sequence Consistency Training (Fixed) |
| [reports/](<reports>) | 3檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 455檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 1檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

兩個精確模型、8px序列、PSF、量測器與全部GMF回傳。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
