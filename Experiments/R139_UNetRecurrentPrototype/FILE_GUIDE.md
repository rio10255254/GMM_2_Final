# main/R139_UNetRecurrentPrototype：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R139_UNetRecurrentPrototype.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：恢復U-Net並把光學放回解碼位置。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R139 因果審查與結果更正](<reports/R139_CAUSAL_AUDIT.md>)
- [R139 U-Net 融合設計與驗證界線](<reports/R139_METHODOLOGY.md>)
- [R139 U-Net 反覆修正模型完整結果](<reports/R139_RESULTS.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [compare_measurements.py](<compare_measurements.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [config/](<config>) | 12檔 | 實驗設定、條件與來源鎖定 |
| [dataset.py](<dataset.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluate_real_measurement.py](<evaluate_real_measurement.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [evaluation/](<evaluation>) | 250檔 | 量測介面、固定參照、設定或比較內容 |
| [final_audit.py](<final_audit.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [formal/](<formal>) | 6檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [FORMAL_RUN.md](<FORMAL_RUN.md>) | 1檔 | R139 U-Net 正式訓練入口 |
| [infer_model.py](<infer_model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [losses.py](<losses.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R139 原型檔案與證據邊界 |
| [model.py](<model.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [MONITOR_R139.cmd](<MONITOR_R139.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [optical/](<optical>) | 2檔 | 光學計算與配套 |
| [README.md](<README.md>) | 1檔 | R139 U-Net 反覆修正原型 |
| [reports/](<reports>) | 6檔 | 原報告、計畫、審查與各階段結論 |
| [results/](<results>) | 3檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 2檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [START_HERE.md](<START_HERE.md>) | 1檔 | R139 正式執行導覽 |
| [START_R139_GPU.cmd](<START_R139_GPU.cmd>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [training_policy.py](<training_policy.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [utils.py](<utils.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [verify_prototype.py](<verify_prototype.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [write_report.py](<write_report.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

原型與正式程式、失敗完整歷程及因果審查。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
