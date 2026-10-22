# main/R147_FullResPSFConsistency：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R147_FullResPSFConsistency.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：修復資料與模型內PSF的尺度用法。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R147 模型內部、歷史對照與改良優先順序](<reports/R147_INTERNAL_AUDIT.md>)
- [下一版模型：以位移、直徑與輪廓為目標的匹配改良計畫](<reports/R147_OPTIMIZATION_PLAN.md>)
- [R147 原尺寸 PSF 成像一致性完整結果](<reports/R147_RESULTS.md>)
- [R147 固定驗證計畫](<reports/R147_VALIDATION_PLAN.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analysis/](<analysis>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [calibration/](<calibration>) | 1檔 | 校正及固定光學來源紀錄 |
| [config/](<config/README.md>) | 4檔 | 實驗設定、條件與來源鎖定 |
| [dataset.py](<dataset.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation/README.md>) | 551檔 | 量測介面、固定參照、設定或比較內容 |
| [infer.py](<infer.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses.py](<losses.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R147 來源、模型與執行身分 |
| [model.py](<model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 1檔 | 光學計算與配套 |
| [README.md](<README.md>) | 1檔 | R147 — 原尺寸 PSF 成像一致性修正 |
| [reports/](<reports/README.md>) | 9檔 | 原報告、計畫、審查與各階段結論 |
| [results_local_verified_copy/](<results_local_verified_copy>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [runs/](<runs/README.md>) | 24檔 | 各次執行的紀錄或完成證據；不憑資料夾名認定已完成 |
| [scripts/](<scripts/README.md>) | 22檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [train.py](<train.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training_policy.py](<training_policy.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [verify_package.py](<verify_package.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [weights/](<weights>) | 1檔 | 模型檔或取得說明；最佳、最後及短測版本需分清 |

## 必要來源與取得界線

同R146場景／PSF、原尺寸光學程式及完整8192模型。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
