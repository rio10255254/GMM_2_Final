# main/R129_OpticalPriorHybrid：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R129_OpticalPriorHybrid.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：恢復光學融合、抗混疊與原圖參考。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R129 完整架構、設計來源與保留檢查](<reports/R129_ARCHITECTURE.md>)
- [R129 連續影像重建與 LSC 位移結果](<reports/R129_CONTINUOUS_LSC_RESULTS.md>)
- [R129 長訓練結果與完成核對](<reports/R129_LONG_TRAINING_RESULTS.md>)
- [R129：保留 V42 主要設計的接入測試](<reports/R129_RESULTS.md>)
- [R129 獨立操作套件與長訓練](<reports/R129_STANDALONE_TRAINING.md>)
- [MOSR論文改寫定稿計畫與備稿資料](<reports/R129_THESIS_FINAL_REWRITE_PLAN_20260920.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R129_OpticalPriorHybrid.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analysis/](<analysis>) | 6檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [config/](<config/README.md>) | 12檔 | 實驗設定、條件與來源鎖定 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R129 manifest |
| [model/](<model>) | 9檔 | 本輪模型程式 |
| [package_source/](<package_source>) | 9檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [README.md](<README.md>) | 1檔 | R129 Optical prior hybrid |
| [reports/](<reports/README.md>) | 13檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results/CONTENTS.md>) | 103檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts/README.md>) | 39檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |

## 必要來源與取得界線

R128來源、25PSF、初始及長訓練模型、固定輸出規則。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
