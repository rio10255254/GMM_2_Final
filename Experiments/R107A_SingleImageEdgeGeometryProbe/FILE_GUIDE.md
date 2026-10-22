# main/R107A_SingleImageEdgeGeometryProbe：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R107A_SingleImageEdgeGeometryProbe.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：固定局部中心只收窄邊緣是否可行。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R107A_SingleImageEdgeGeometryProbe 研究保存清單](<MANIFEST.md>)
- [R107A Single-Image Edge Geometry Probe](<README.md>)
- [R107A 單張局部邊界幾何設計](<design/R107A_DESIGN_ZH.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 1檔 | 實驗設定、條件與來源鎖定 |
| [data/](<data>) | 1檔 | 資料相關原件、清單或固定來源；內容身分由設定與原說明確認 |
| [design/](<design>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [inference/](<inference>) | 2檔 | 模型重建程式 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R107A_SingleImageEdgeGeometryProbe 研究保存清單 |
| [model/](<model>) | 1檔 | 本輪模型程式 |
| [README.md](<README.md>) | 1檔 | R107A Single-Image Edge Geometry Probe |
| [requirements.txt](<requirements.txt>) | 1檔 | 原說明／報告／歷史紀錄 |
| [scripts/](<scripts>) | 6檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [training/](<training>) | 3檔 | 訓練程式與配套 |
| [validation/](<validation>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

5000／512場景生成、解析控制及後續學習設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
