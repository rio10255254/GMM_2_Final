# main/R44_UniversalBoundaryMotionFidelity：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R44_UniversalBoundaryMotionFidelity.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：直接約束顯微結構隨已知位移正確移動。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R44C 探針計畫 — 分族平衡邊界位移](<reports/R44C_PROBE_PLAN.md>)
- [R44D 診斷 — 分族與位移尺度盤點](<reports/R44D_FAMILY_DIAGNOSTIC.md>)
- [R44E 大區塊與混合場景專項探針](<reports/R44E_TARGETED_PROBE.md>)
- [R44F 診斷 — 大區塊與混合場景錯誤解剖](<reports/R44F_ERROR_DIAGNOSTIC.md>)
- [R44G 邊界形狀體檢](<reports/R44G_BOUNDARY_SHAPE_METRICS.md>)
- [R44H Step 0 / Step A — R44B 家族權重平均探測](<reports/R44H_STEPA_FAMILY_AVERAGE.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R44_UniversalBoundaryMotionFidelity.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [ARCHIVE_POINTER_20260824.md](<ARCHIVE_POINTER_20260824.md>) | 1檔 | R44 歷史封存與恢復入口 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R44 Manifest |
| [README.md](<README.md>) | 1檔 | R44 — 通用顯微邊界位移忠實度 |
| [reports/](<reports>) | 11檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 9檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 14檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 12檔 | 原檢查程式；不是研究結果本身 |

## 必要來源與取得界線

七類連續場景、R42及各老師／起點、每個支線實際設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
