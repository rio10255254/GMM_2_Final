# lab/R60_SEMTruthBoundaryTraining 研究與重做紀錄

修復實拍裁切答案、亮暗方向與真值權重

方向與取樣修正後短測改善，完整歷史及SEM訓練依賴均保留

## 必要來源

保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。

## 影像保存理由

共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [R60_BOUNDARY_DATA_MODEL_AUDIT_20260622.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/R60_BOUNDARY_DATA_MODEL_AUDIT_20260622.md)
- [R60_BOUNDARY_FOCUS_TRAINING_STATUS_20260622.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/R60_BOUNDARY_FOCUS_TRAINING_STATUS_20260622.md)
- [R60_BOUNDARY_ROOT_CAUSE_ANALYSIS_20260622.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/R60_BOUNDARY_ROOT_CAUSE_ANALYSIS_20260622.md)
- [SYNTHETIC_PHANTOM_VALIDATION_20260623.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/SYNTHETIC_PHANTOM_VALIDATION_20260623.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e002_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e003_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e004_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e004_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e005_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e008_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e008_mtb064_20260622_epochs/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/fullish_e012_mtb256_epoch_scan_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/fullish_e012_mtb256_polarityfix_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/grouped_split_e004_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/grouped_strat_e004_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/grouped_strat_e004_mtb064_20260622_epochs/R60_AUTOMATED_ROUNDS_STATUS.md)
- [R60_AUTOMATED_ROUNDS_STATUS.md](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/verify_existing_polarityfix_e004/R60_AUTOMATED_ROUNDS_STATUS.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
