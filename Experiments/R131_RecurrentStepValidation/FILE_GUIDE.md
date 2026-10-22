# main/R131_RecurrentStepValidation：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R131_RecurrentStepValidation.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：同一R129模型使用0到4次修正的得失。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R131：為何展示影像只有半邊變清楚](<reports/R131_BOUNDARY_OUTPUT_AUDIT.md>)
- [R131 固定比較方法](<reports/R131_METHODOLOGY.md>)
- [R131：R129 四次反覆修復的實際驗證](<reports/R131_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 2檔 | 實驗設定、條件與來源鎖定 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R131 Manifest |
| [README.md](<README.md>) | 1檔 | R131 四次修復驗證 |
| [reports/](<reports>) | 7檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 8檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 9檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

同一長訓練權重、201原圖及每個修正次數讀值。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
