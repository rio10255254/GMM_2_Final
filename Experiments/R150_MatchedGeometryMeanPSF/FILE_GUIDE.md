# main/R150_MatchedGeometryMeanPSF：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R150_MatchedGeometryMeanPSF.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：保持架構，測新排列與訓練推論共用平均PSF。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R150 Methodology](<reports/R150_METHODOLOGY.md>)
- [R150 完整實拍驗證結果](<reports/R150_REAL_VALIDATION_RESULTS.md>)
- [R150 Training Results](<reports/R150_RESULTS.md>)
- [R150 Validation Plan](<reports/R150_VALIDATION_PLAN.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [calibration/](<calibration>) | 1檔 | 校正及固定光學來源紀錄 |
| [config/](<config>) | 5檔 | 實驗設定、條件與來源鎖定 |
| [dataset.py](<dataset.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation>) | 671檔 | 量測介面、固定參照、設定或比較內容 |
| [infer.py](<infer.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses.py](<losses.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R150 Manifest |
| [model.py](<model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 1檔 | 光學計算與配套 |
| [README.md](<README.md>) | 1檔 | R150 — Matched Geometry + Mean PSF |
| [reports/](<reports>) | 5檔 | 原報告、計畫、審查與各階段結論 |
| [scripts/](<scripts>) | 13檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [train.py](<train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training_policy.py](<training_policy.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [verify_package.py](<verify_package.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

R149鎖定資料、原全局要求、8192模型及固定930驗收。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
