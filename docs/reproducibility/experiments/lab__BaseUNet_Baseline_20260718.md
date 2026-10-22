# lab/BaseUNet_Baseline_20260718 研究與重做紀錄


2026-10-21保存補充：原30輪時程實際採用最佳第12輪，完整訓練9857／驗證1397份，使用相同固定PSF與L1+0.20*(1-SSIM)。原15輪與30輪最佳、整張與切片輸出分開；舊表的V42欄名不代表此處實際是V42模型。 [完整來源與比較脈絡](../lab_comparisons/README.md)。


以基礎U-Net作參數與訓練資料受控比較



不同資料量／固定光學／切片與輪次版本分開；輸出報告沿用V42欄名需核對實際方法身分



## 必要來源



分清縮小資料、完整資料、固定PSF與分塊30輪各版；保留各自資料清單、Base U-Net權重、原推論設定及五方法原表。舊輸出沿用V42欄名，方法身分必須回到實際模型與設定。



## 影像保存理由



沿原Raw固定區域與同一成像條件選代表圖，保留光學、分塊及訓練版本差異與不利結果；原表優先，不能因沿用V42欄名而誤認方法。



## 原始方法與結果



下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。



- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_fixed_psf/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_fixed_psf/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_e15_tiled/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_e15_tiled/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：基礎 U-Net 重新訓練與位移穩定性檢查](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/BASE_UNET_RETEST_SUMMARY_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_0p5/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_0p5/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p0/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p0/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p5/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p5/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_2p0/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_2p0/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_v2/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_v2/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)



## 重做與驗證範圍



程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。

本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。

任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。



## 2026年10月16日保存核對



本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。



本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。



D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。


## 2026-10-22：這一輪在整條研究中的位置

[按R1至R153查找](../lineage/ROUND_NUMBER_MAP.md)／[本研究線的來源、得失與後續](../lineage/LAB_SYSTEM.md)。本輪上方已改為具體必要來源；原日期的保存、失敗與執行證據保留各自範圍，不以文件數或標號連續性冒稱全部歷史已重現。
