# main/R26NewPSFCheck：檔案怎麼找

[本輪研究卡](<../../docs/reproducibility/experiments/main__R26NewPSFCheck.md>) · [全部研究分區](<../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../docs/reproducibility/STATUS.md>)

**研究問題：新PSF重訓、正式光學流程與交付版本的關係。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [ROUND26_STEP_RECOVERY 決策摘要](<artifacts/package_mainline_realign_20260326_234441/backups/內部檔案/Traing_Progress/organized_20260316/round26/selected/reports/ROUND26_STEP_RECOVERY_DECISION_20260316_191450.md>)
- [ROUND26_STEP_RECOVERY 決策摘要](<artifacts/package_mainline_realign_20260326_234441/backups/輸出結果/訓練結果/organized_20260316/round26/selected/reports/ROUND26_STEP_RECOVERY_DECISION_20260316_191450.md>)
- [New PSF Formal R26 Compare](<formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md>)
- [ROUND26_STEP_RECOVERY Decision Memo](<package_cleanup_release_archive_20260327_122202/內部檔案/Traing_Progress/organized_20260316/round26/selected/reports/ROUND26_STEP_RECOVERY_DECISION_20260316_191450.md>)
- [ROUND26_STEP_RECOVERY Decision Memo](<package_cleanup_release_archive_20260327_122202/輸出結果/訓練結果/organized_20260316/round26/selected/reports/ROUND26_STEP_RECOVERY_DECISION_20260316_191450.md>)
- [R26 外部驗證完整總報告](<package_final_cleanup_archive_20260327_170935/輸出結果/驗證分析/archive/validation_complete_non_single/reports/R26_完整驗證總報告.md>)

其餘原報告見[本輪完整研究卡](<../../docs/reproducibility/experiments/main__R26NewPSFCheck.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [ablation_single_sample/](<ablation_single_sample>) | 5檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [artifacts/](<artifacts>) | 37檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [formal_newpsf_candidate/](<formal_newpsf_candidate>) | 32檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [MANIFEST.md](<MANIFEST.md>) | 1檔 | R26 — New PSF Check |
| [package_cleanup_release_archive_20260327_122202/](<package_cleanup_release_archive_20260327_122202>) | 20檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [package_final_cleanup_archive_20260327_170935/](<package_final_cleanup_archive_20260327_170935>) | 26檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [package_policy_transition/](<package_policy_transition>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [package_repro_validation/](<package_repro_validation>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [psf_audit/](<psf_audit>) | 1檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [pure_psf_control/](<pure_psf_control>) | 23檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [README.md](<README.md>) | 1檔 | R26NewPSFCheck — 實驗 Sandbox 說明文件 |
| [reports/](<reports/README.md>) | 6檔 | 原報告、計畫、審查與各階段結論 |
| [root_cause_centering/](<root_cause_centering>) | 13檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [Tools/](<Tools>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |

## 必要來源與取得界線

新舊PSF、實際起始模型、原始光學來源、各子研究設定。

[按用途取得原件](<../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
