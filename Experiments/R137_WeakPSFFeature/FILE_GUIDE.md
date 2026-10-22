# main/R137_WeakPSFFeature：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R137_WeakPSFFeature.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：以低強度光學線索輔助原尺寸模型。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R137 弱 PSF 特徵測試結果](<reports/R137_RESULTS.md>)
- [R137 執行時間解讀補充](<reports/R137_RUNTIME_SCOPE_ADDENDUM.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [batch_prediction.py](<batch_prediction.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [calibration/](<calibration>) | 1檔 | 校正及固定光學來源紀錄 |
| [CHECK_STATUS.cmd](<CHECK_STATUS.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [compare_measurements.py](<compare_measurements.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [config/](<config>) | 6檔 | 實驗設定、條件與來源鎖定 |
| [config_r137_psf.yaml](<config_r137_psf.yaml>) | 1檔 | 設定／清單／數值紀錄；依欄位判讀 |
| [dataset_r137_psf.py](<dataset_r137_psf.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluate_generated.py](<evaluate_generated.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluate_real_measurement.py](<evaluate_real_measurement.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation>) | 130檔 | 量測介面、固定參照、設定或比較內容 |
| [final_audit.py](<final_audit.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [infer_r137_psf.py](<infer_r137_psf.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses_r137_psf.py](<losses_r137_psf.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | 原說明／報告／歷史紀錄 |
| [model_r137_psf.py](<model_r137_psf.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 2檔 | 光學計算與配套 |
| [preflight_check.py](<preflight_check.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [README.md](<README.md>) | 1檔 | R137 弱 PSF 特徵測試 |
| [reports/](<reports>) | 4檔 | 原報告、計畫、審查與各階段結論 |
| [requirements.txt](<requirements.txt>) | 1檔 | 原說明／報告／歷史紀錄 |
| [results/](<results>) | 13檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 2檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [START_R137.cmd](<START_R137.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [train_r137_psf.py](<train_r137_psf.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [write_report.py](<write_report.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

R130資料、精確25PSF、8192模型及共同930原圖。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
