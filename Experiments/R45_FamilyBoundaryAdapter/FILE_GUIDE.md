# main/R45_FamilyBoundaryAdapter：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R45_FamilyBoundaryAdapter.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：用小修正或分族選擇承接R44分散能力。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R45B 老師殘差與理想分族診斷](<reports/R45B_TEACHER_DIAGNOSTICS.md>)
- [R45C 分區理想上限與殘差診斷](<reports/R45C_REGION_ORACLE.md>)
- [R45C 分區理想上限與殘差診斷](<reports/R45C_REGION_ORACLE_SMOKE.md>)
- [R45 分族邊界校正模組結果](<reports/R45_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [ARCHIVE_POINTER_20260824.md](<ARCHIVE_POINTER_20260824.md>) | 1檔 | R45 歷史封存與恢復入口 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R45 產物清單 |
| [README.md](<README.md>) | 1檔 | R45 分族邊界校正模組 |
| [reports/](<reports>) | 4檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 2檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 8檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 4檔 | 原檢查程式；不是研究結果本身 |

## 必要來源與取得界線

R44各候選與老師、逐張及逐族結果、固定分組。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
