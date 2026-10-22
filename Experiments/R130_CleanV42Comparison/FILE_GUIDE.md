# main/R130_CleanV42Comparison：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R130_CleanV42Comparison.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：以乾淨來源從頭訓練V42作實用比較。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R130 快速、乾淨的 V42 比較設計](<reports/R130_DESIGN.md>)
- [R130：乾淨重訓 V42 與固定 R129 的真實影像比較](<reports/R130_RESULTS.md>)
- [R61 到 R130：目前模型為何形成這個設計](<reports/R61_R130_DESIGN_REVIEW.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 7檔 | 實驗設定、條件與來源鎖定 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R130 manifest |
| [model/](<model>) | 5檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R130 Clean V42 comparison |
| [reports/](<reports>) | 5檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 7檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 20檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [training/](<training>) | 3檔 | 訓練程式與配套 |
| [validation/](<validation>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

512生成來源、官方／專案程式身分、固定模型與201原圖。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
