# main/R119_SequenceGeometryValidation：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R119_SequenceGeometryValidation.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：檢查同物體序列訓練與邊界位置。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R119 closeout](<reports/CLOSEOUT.md>)
- [R119 causal audit and corrections](<reports/R119_CAUSAL_AUDIT.md>)
- [R119：固定形狀的模糊、亮度與位移控制檢查](<reports/R119_CONTROLLED_BOUNDARY_FACTORS.md>)
- [R119：位置修正是否造成跨曝光的輪廓膨脹](<reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md>)
- [R109 與 R119：同一影像、三種邊界讀法與處理路徑](<reports/R119_R109_READOUT_COMPARISON.md>)
- [R119 formal result](<reports/R119_RESULTS.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R119_SequenceGeometryValidation.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analysis/](<analysis>) | 48檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [config/](<config>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 3檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [Infer.py](<Infer.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R119 Sequence Geometry Validation |
| [model/](<model>) | 2檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R119 Sequence Geometry Validation |
| [reports/](<reports>) | 7檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 12檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 5檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 3檔 | 原檢查程式；不是研究結果本身 |
| [Train.py](<Train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training/](<training>) | 5檔 | 訓練程式與配套 |
| [validation/](<validation>) | 24檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

真正被讀取的訓練觀測、E42、逐筆抽樣與後續因果審查。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
