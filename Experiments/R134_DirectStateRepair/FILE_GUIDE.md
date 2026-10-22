# main/R134_DirectStateRepair：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R134_DirectStateRepair.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：直接修正影像狀態並避免8bit存檔誤導。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R134 校準與資料准入現況](<reports/R134_CALIBRATION_STATUS.md>)
- [R134：第16至17張側向偏移的原因](<reports/R134_CROSS_AXIS_DIAGNOSIS.md>)
- [每代長訓練模型的獨立套件要求](<reports/R134_LONG_PACKAGE_SPEC.md>)
- [R134 固定短測方法](<reports/R134_METHODOLOGY.md>)
- [R134 P1：保留量測精度的完整驗證與訓練](<reports/R134_PRECISION_REVALIDATION.md>)
- [R134 執行結果與目前狀態](<reports/R134_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 6檔 | 實驗設定、條件與來源鎖定 |
| [dataset134.py](<dataset134.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R134 Manifest |
| [net/](<net>) | 8檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [objectives.py](<objectives.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [package_templates/](<package_templates>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [precision_revision/](<precision_revision>) | 45檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [README.md](<README.md>) | 1檔 | R134 直接影像狀態修正 |
| [reports/](<reports>) | 6檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 18檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [rt.py](<rt.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [scripts/](<scripts>) | 27檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [STATUS_R134.cmd](<STATUS_R134.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [tiled.py](<tiled.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [train_core.py](<train_core.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [validation/](<validation>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

P1精確模型、保存精度、兩起點短測及長訓練資料。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
