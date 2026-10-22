# main/R140v2_StableUNet：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R140v2_StableUNet.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：獨立重新封裝穩定U-Net。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R139 失穩原因與 R140v2 修正紀錄](<reports/R140v2_CAUSAL_REPAIR.md>)
- [R140v2 PSF 權重未自適應的因果診斷](<reports/R140v2_PSF_GATE_CAUSAL_AUDIT.md>)
- [R140v2 U-Net 反覆修正模型完整結果](<reports/R140v2_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [compare_measurements.py](<compare_measurements.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [config/](<config>) | 9檔 | 實驗設定、條件與來源鎖定 |
| [dataset.py](<dataset.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluate_real_measurement.py](<evaluate_real_measurement.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation>) | 310檔 | 量測介面、固定參照、設定或比較內容 |
| [final_audit.py](<final_audit.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [formal/](<formal>) | 5檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [FORMAL_RUN.md](<FORMAL_RUN.md>) | 1檔 | R140v2 訓練與驗證固定規格 |
| [infer_model.py](<infer_model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses.py](<losses.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R140v2_StableUNet 研究保存清單 |
| [model.py](<model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 2檔 | 光學計算與配套 |
| [README.md](<README.md>) | 1檔 | R140v2_StableUNet 研究入口 |
| [reports/](<reports>) | 17檔 | 原報告、計畫、審查與各階段結論 |
| [scripts/](<scripts>) | 2檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [START_HERE.md](<START_HERE.md>) | 1檔 | R140v2 使用入口 |
| [training_policy.py](<training_policy.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [write_report.py](<write_report.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

凍結程式、最後模型、PSF與R130來源。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
