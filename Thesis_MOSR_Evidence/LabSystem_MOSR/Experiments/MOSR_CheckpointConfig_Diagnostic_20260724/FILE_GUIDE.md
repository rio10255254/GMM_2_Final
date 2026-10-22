# lab/MOSR_CheckpointConfig_Diagnostic_20260724：檔案怎麼找

[Lab逐輪必要來源與代表模型核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)

[本輪研究卡](<../../../../docs/reproducibility/experiments/lab__MOSR_CheckpointConfig_Diagnostic_20260724.md>) · [全部研究分區](<../../../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../../../docs/reproducibility/STATUS.md>)

**研究問題：拆解EDSR與MOSR位移差異的來源。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [EDSR 與 MOSR 位移結果診斷](<diagnosis/DIAGNOSTIC_REPORT_zh-TW.md>)

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [diagnose_edsr_vs_mosr.py](<diagnose_edsr_vs_mosr.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [diagnosis/](<diagnosis>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [evaluation/](<evaluation>) | 5檔 | 量測介面、固定參照、設定或比較內容 |

## 必要來源與取得界線

保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。。

[按用途取得原件](<../../../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
