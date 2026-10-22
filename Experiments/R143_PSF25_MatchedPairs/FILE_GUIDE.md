# main/R143_PSF25_MatchedPairs：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R143_PSF25_MatchedPairs.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：以模型同一25PSF形成訓練配對。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R143 實測 PSF 配對資料完整訓練結果](<reports/R143_RESULTS.md>)
- [R143 位移與尺寸穩定性深層診斷](<reports/R143_STABILITY_DIAGNOSIS.md>)
- [R143 固定驗證計畫](<reports/R143_VALIDATION_PLAN.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analysis/](<analysis>) | 13檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [calibration/](<calibration>) | 1檔 | 校正及固定光學來源紀錄 |
| [config/](<config>) | 5檔 | 實驗設定、條件與來源鎖定 |
| [dataset.py](<dataset.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation>) | 370檔 | 量測介面、固定參照、設定或比較內容 |
| [infer.py](<infer.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses.py](<losses.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R143 實驗來源與保存 |
| [model.py](<model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 2檔 | 光學計算與配套 |
| [README.md](<README.md>) | 1檔 | R143 — 25 顆實測 PSF 配對資料完整訓練 |
| [reports/](<reports>) | 7檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 1檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 15檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [train.py](<train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training_policy.py](<training_policy.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [verify_package.py](<verify_package.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [weights/](<weights>) | 1檔 | 模型檔或取得說明；最佳、最後及短測版本需分清 |

## 必要來源與取得界線

768原場景、舊25PSF、配對標記與8192模型。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
