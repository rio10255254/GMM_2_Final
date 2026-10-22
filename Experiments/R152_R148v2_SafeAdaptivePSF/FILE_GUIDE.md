# main/R152_R148v2_SafeAdaptivePSF：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R152_R148v2_SafeAdaptivePSF.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：保存R148v2效益並加入有作用的論文光學模組。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R152 模型架構與完整實驗資料紀錄](<reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md>)
- [R152完整訓練影像生成程式與重新生成核對](<reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md>)
- [R152：保留 R148v2 效果的自適應 PSF 安全擴充](<reports/R152_DESIGN_AND_PREFLIGHT.md>)
- [R152 完整實拍驗證](<reports/R152_FULL_REAL_VALIDATION.md>)
- [R152 與 RAW 完整研究設計及驗證紀錄](<reports/R152_RAW_FULL_RECORD_20261002/REPORT.md>)
- [R152與RAW研究紀錄閱讀入口](<reports/R152_RAW_FULL_RECORD_20261002/START_HERE.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R152_R148v2_SafeAdaptivePSF.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [base_model.py](<base_model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [calibration/](<calibration>) | 2檔 | 校正及固定光學來源紀錄 |
| [config/](<config/README.md>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [dataset.py](<dataset.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses.py](<losses.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R152_R148v2_SafeAdaptivePSF 研究保存清單 |
| [model.py](<model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 2檔 | 光學計算與配套 |
| [README.md](<README.md>) | 1檔 | R152 — Safe Adaptive PSF Extension of R148v2 |
| [reports/](<reports/README.md>) | 52檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results/README.md>) | 66檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts/README.md>) | 15檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [train.py](<train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

可獨立重建的9216影像配方、精確PSF、基底／擴充模型、930原圖與完整讀值。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
