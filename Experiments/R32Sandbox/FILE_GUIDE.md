# main/R32Sandbox：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R32Sandbox.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：加入真實影像訓練是否改善R30。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [ROUND32_DOMAIN_CAPACITY AUDIT_0P8 Summary](<reports/ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_SUMMARY_20260319_183506.md>)
- [Process Probe Audit](<reports/ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_r32_real_eq_finetune_20260319_183506.md>)
- [ROUND32_DOMAIN_CAPACITY AUDIT_8P0 Summary](<reports/ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_SUMMARY_20260319_183546.md>)
- [Process Probe Audit](<reports/ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_r32_real_eq_finetune_20260319_183546.md>)
- [ROUND32_DOMAIN_CAPACITY Decision Memo](<reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md>)
- [ROUND32_DOMAIN_CAPACITY Summary](<reports/ROUND32_DOMAIN_CAPACITY_SUMMARY_20260319_183506.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R32Sandbox.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [ARCHIVE_POINTER_20260824.md](<ARCHIVE_POINTER_20260824.md>) | 1檔 | R32 歷史封存與恢復入口 |
| [artifacts/](<artifacts>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [external_compare/](<external_compare>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R32 — Domain Capacity Sandbox |
| [Model/](<Model>) | 9檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [README.md](<README.md>) | 1檔 | R32 Sandbox |
| [reports/](<reports>) | 8檔 | 原報告、計畫、審查與各階段結論 |
| [runtime/](<runtime>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [Tools/](<Tools>) | 4檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

R30起始模型、真實訓練影像、固定合成資料與外部GMF原始回傳。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
