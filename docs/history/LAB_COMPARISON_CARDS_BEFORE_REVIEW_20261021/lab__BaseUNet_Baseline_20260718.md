# lab/BaseUNet_Baseline_20260718 研究與重做紀錄

以基礎U-Net作參數與訓練資料受控比較

不同資料量／固定光學／切片與輪次版本分開；輸出報告沿用V42欄名需核對實際方法身分

## 必要來源

保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。

## 影像保存理由

共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_fixed_psf/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_fixed_psf/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_e15_tiled/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_e15_tiled/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：基礎 U-Net 重新訓練與位移穩定性檢查](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/BASE_UNET_RETEST_SUMMARY_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_0p5/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_0p5/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p0/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p0/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p5/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_1p5/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_2p0/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/smoothing_control/sigma_2p0/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_v2/displacement_audit/UNIFIED_AUDIT_REPORT_TW.md>)
- [原始報告：四組位移實驗 Raw 鎖定、V42 盲化稽核](<../../../LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_v2/displacement_audit/candidate/CANDIDATE_READOUT_TW.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。
