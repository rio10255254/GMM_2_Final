# main/R130_Clean：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R130_Clean.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：移除光學與放大，採原尺寸純神經模型。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R130-Clean 完整結果](<reports/R130_CLEAN_RESULTS.md>)
- [R130-Clean 訓練來源](<reports/TRAINING_PROVENANCE.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [compare_measurements.py](<compare_measurements.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [config/](<config>) | 6檔 | 實驗設定、條件與來源鎖定 |
| [config_r130_clean.yaml](<config_r130_clean.yaml>) | 1檔 | 設定／清單／數值紀錄；依欄位判讀 |
| [dataset_r130_clean.py](<dataset_r130_clean.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [DELIVERY.md](<DELIVERY.md>) | 1檔 | R130-Clean 完整交付入口 |
| [evaluate_generated.py](<evaluate_generated.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluate_real_measurement.py](<evaluate_real_measurement.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation>) | 70檔 | 量測介面、固定參照、設定或比較內容 |
| [infer_r130_clean.py](<infer_r130_clean.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses_r130_clean.py](<losses_r130_clean.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R130-Clean 執行入口 |
| [model_r130_clean.py](<model_r130_clean.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 3檔 | 光學計算與配套 |
| [preflight_check.py](<preflight_check.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [profile_r130_clean.py](<profile_r130_clean.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [README.md](<README.md>) | 1檔 | R130-Clean 原尺寸從零訓練 |
| [reports/](<reports>) | 8檔 | 原報告、計畫、審查與各階段結論 |
| [requirements.txt](<requirements.txt>) | 1檔 | 原說明／報告／歷史紀錄 |
| [results/](<results>) | 13檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [runs/](<runs>) | 1檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts>) | 3檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [START_R130.cmd](<START_R130.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [train_r130_clean.py](<train_r130_clean.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [write_report.py](<write_report.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

768來源的精確白名單、固定最後模型與量測設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
