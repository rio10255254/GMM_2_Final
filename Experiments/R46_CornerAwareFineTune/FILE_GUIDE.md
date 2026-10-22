# main/R46_CornerAwareFineTune：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R46_CornerAwareFineTune.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：補強角點與直角同時檢查位移。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R46 失敗成因診斷](<reports/R46_FAILURE_DIAGNOSIS.md>)
- [R46 結果 — a025 邊角細節微調(路徑 B)](<reports/R46_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [ARCHIVE_POINTER_20260824.md](<ARCHIVE_POINTER_20260824.md>) | 1檔 | R46 歷史封存與恢復入口 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R46 Manifest |
| [README.md](<README.md>) | 1檔 | Round 46 — a025 邊角細節微調(路徑 B:既有 hyperparam 強化版) |
| [reports/](<reports>) | 2檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 9檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 8檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

角點來源、前代模型、各訓練設定與完整結果。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
