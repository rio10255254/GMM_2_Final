# main/R109_StagedMidpointWidthScratch：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R109_StagedMidpointWidthScratch.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：先固定偵測，再學受限位移與單調寬度。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R108C 到 R109：設計與證據鏈](<reports/R108C_TO_R109_DECISION_CHAIN_ZH.md>)
- [R109 E48 最終選擇](<reports/R109_FINAL_SELECTION_ZH.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 1檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 1檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [inference/](<inference>) | 1檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R109_StagedMidpointWidthScratch 研究保存清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R109 Staged Midpoint-Width Scratch Model |
| [reports/](<reports>) | 2檔 | 原報告、計畫、審查與各階段結論 |
| [requirements.txt](<requirements.txt>) | 1檔 | 原說明／報告／歷史紀錄 |
| [results/](<results>) | 4檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 9檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [training/](<training>) | 3檔 | 訓練程式與配套 |
| [validation/](<validation>) | 5檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

5000／512程序資料、兩階段設定及E48模型。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
