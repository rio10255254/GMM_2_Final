# lab/R60_SEMTruthBoundaryTraining 研究與重做紀錄

[全部實驗](../EXPERIMENTS.md) · [LabSystem：校正、資料與專屬模型](../routes/lab.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

修復實拍裁切答案、亮暗方向與真值權重

方向與取樣修正後短測改善，完整歷史及SEM訓練依賴均保留

## 必要來源

保留同樣本SEM表、71個實拍裁切、來源亮暗方向修正、重複12次成852配對及1024合成錨點；錯方向／過低實拍權重舊版與修正版分開，並保留CD門檻與PSF-forward停用理由。

## 影像保存理由

保留同位置SEM、實拍、訓練答案與重建，以及錯亮暗方向／半量修正對照；SEM參與答案形成須同時標示，不能稱獨立SEM準確度。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R60 Boundary Data / Model Audit - 2026-06-22](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/R60_BOUNDARY_DATA_MODEL_AUDIT_20260622.md>)
- [原始報告：R60 Boundary-Focus Training Status - 2026-06-22](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/R60_BOUNDARY_FOCUS_TRAINING_STATUS_20260622.md>)
- [原始報告：R60 Boundary Root Cause Analysis - 2026-06-22](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/R60_BOUNDARY_ROOT_CAUSE_ANALYSIS_20260622.md>)
- [原始報告：Synthetic Phantom Boundary Validation - 2026-06-23](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/SYNTHETIC_PHANTOM_VALIDATION_20260623.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e002_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e003_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e004_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e004_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e005_mtb256_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e008_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/boundary_focus_e008_mtb064_20260622_epochs/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/fullish_e012_mtb256_epoch_scan_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/fullish_e012_mtb256_polarityfix_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/grouped_split_e004_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/grouped_strat_e004_mtb064_20260622/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/grouped_strat_e004_mtb064_20260622_epochs/R60_AUTOMATED_ROUNDS_STATUS.md>)
- [原始報告：R60 Automated Round Status](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/r60_automated_rounds/verify_existing_polarityfix_e004/R60_AUTOMATED_ROUNDS_STATUS.md>)

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


---

[上一個閱讀入口：lab/R59_CDClosedLoopBoundaryLayer](lab__R59_CDClosedLoopBoundaryLayer.md) · [回本分區](../routes/lab.md) · [下一個閱讀入口：lab/R61_BoundaryGeneralizationUniversal](lab__R61_BoundaryGeneralizationUniversal.md)
