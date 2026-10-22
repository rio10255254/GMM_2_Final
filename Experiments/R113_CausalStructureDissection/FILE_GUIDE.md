# main/R113_CausalStructureDissection：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R113_CausalStructureDissection.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：拆開渲染能力、學到控制、訓練軌跡與量法。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [R113_CausalStructureDissection 研究保存清單](<MANIFEST.md>)
- [R113 corrected ring-measurement findings](<MEASUREMENT_QA_FINDINGS.md>)
- [R113 最終發現](<R113_FINDINGS_ZH.md>)
- [R113 Causal Structure Dissection](<README.md>)
- [R113 模型與訓練影像超深度剖析](<deep_audit/DEEP_AUDIT_FINDINGS_ZH.md>)
- [R114 Confidence-Gated Recoverable MOSR：完整總計畫](<deep_audit/R114_MASTER_PLAN_ZH.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R113_CausalStructureDissection.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [config/](<config>) | 2檔 | 實驗設定、條件與來源鎖定 |
| [deep_audit/](<deep_audit>) | 17檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R113_CausalStructureDissection 研究保存清單 |
| [MEASUREMENT_QA_FINDINGS.md](<MEASUREMENT_QA_FINDINGS.md>) | 1檔 | R113 corrected ring-measurement findings |
| [next_probe/](<next_probe>) | 18檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [R113_CAUSAL_DISSECTION.ipynb](<R113_CAUSAL_DISSECTION.ipynb>) | 1檔 | 原配套檔案 |
| [R113_FINDINGS_ZH.md](<R113_FINDINGS_ZH.md>) | 1檔 | R113 最終發現 |
| [README.md](<README.md>) | 1檔 | R113 Causal Structure Dissection |
| [results/](<results>) | 5檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [scripts/](<scripts>) | 29檔 | 執行、整理或檢查程式；需讀原用途，不能全部直接執行 |
| [tests/](<tests>) | 1檔 | 原檢查程式；不是研究結果本身 |

## 必要來源與取得界線

V42／R61／R109固定模型、匹配來源及每個干預設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
