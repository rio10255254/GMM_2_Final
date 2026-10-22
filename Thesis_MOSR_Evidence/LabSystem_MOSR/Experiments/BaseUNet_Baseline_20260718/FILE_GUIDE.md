# lab/BaseUNet_Baseline_20260718：檔案怎麼找

[本輪研究卡](<../../../../docs/reproducibility/experiments/lab__BaseUNet_Baseline_20260718.md>) · [全部研究分區](<../../../../docs/reproducibility/EXPERIMENTS.md>) · [目前保存狀態](<../../../../docs/reproducibility/STATUS.md>)

**研究問題：以基礎U-Net作參數與訓練資料受控比較。**

本頁按GitHub當前主版本的實際目錄編排，不改原報告、模型、數值或檔案位置。目錄數量不包含版本附件及僅在本機的資料，也不能代表這一輪來源已全部查完。

## 先讀原文件

- [四組位移實驗 Raw 鎖定、V42 盲化稽核](<results/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [四組位移實驗 Raw 鎖定、V42 盲化稽核](<results/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [四組位移實驗 Raw 鎖定、V42 盲化稽核](<results_fixed_psf/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [四組位移實驗 Raw 鎖定、V42 盲化稽核](<results_fixed_psf/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [四組位移實驗 Raw 鎖定、V42 盲化稽核](<results_full_data/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [四組位移實驗 Raw 鎖定、V42 盲化稽核](<results_full_data/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

其餘原報告見[本輪完整研究卡](<../../../../docs/reproducibility/experiments/lab__BaseUNet_Baseline_20260718.md>)。

## 進入實際檔案

| 區域／原檔 | GitHub主版本所見 | 怎麼讀 |
|---|---:|---|
| [analyze_base_unet_baseline.py](<analyze_base_unet_baseline.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [analyze_base_unet_edge_stability.py](<analyze_base_unet_edge_stability.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [analyze_gaussian_smoothing_control.py](<analyze_gaussian_smoothing_control.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [compare_base_unet_retests.py](<compare_base_unet_retests.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [infer_base_unet.py](<infer_base_unet.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [make_base_unet_qualitative_figure.m](<make_base_unet_qualitative_figure.m>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [make_base_unet_retest_figures.m](<make_base_unet_retest_figures.m>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [results/](<results>) | 2檔 | 原結果、量測、檢查紀錄與歷史輸出；依原報告判讀 |
| [results_fixed_psf/](<results_fixed_psf>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [results_full_data/](<results_full_data>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [results_full_data_fixed_psf_e15_tiled/](<results_full_data_fixed_psf_e15_tiled>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [results_full_data_fixed_psf_tiled_e30/](<results_full_data_fixed_psf_tiled_e30>) | 19檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [results_full_data_fixed_psf_v2/](<results_full_data_fixed_psf_v2>) | 2檔 | 保留原名稱的研究子區；用途回到原報告及區內說明 |
| [run_base_unet_displacement_audit.py](<run_base_unet_displacement_audit.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [run_gaussian_smoothing_control.py](<run_gaussian_smoothing_control.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |
| [train_base_unet.py](<train_base_unet.py>) | 1檔 | 程式／操作入口（不代表可直接執行） |

## 必要來源與取得界線

保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。。

[按用途取得原件](<../../../../docs/reproducibility/ASSET_GUIDE.md>) · [生成方法與固定來源](<../../../../docs/reproducibility/GENERATION_GUIDE.md>) · [缺件及重做限制](<../../../../docs/reproducibility/KNOWN_GAPS.md>)

原README或當年MANIFEST列出的完整本機內容，可能有部分放在GitHub版本附件。GitHub這一層沒有大模型或影像，不代表可以用後來版本代替，也不代表原包已失去該檔；先查對應取得說明。
