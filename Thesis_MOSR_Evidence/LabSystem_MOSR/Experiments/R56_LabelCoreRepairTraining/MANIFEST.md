# R56 Label-Core Repair Training Manifest

## Experiment

- ID: R56_LabelCoreRepairTraining
- Status: completed; real checkboard corner gate failed; not adopted
- Created: 2026-06-18
- Scope: LabSystem_MOSR only; label-core repair validation

## Source Scripts

- `scripts/launch_r56.py`
- `scripts/start_r56_formal_training.ps1`
- `scripts/run_r56_checkboard_reconstruction.py`
- `scripts/validate_r56_checkboard_corner_geometry.py`

## Data Packages

- Train: `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration/r53_realistic_calibrated_train_6000`
- Validation pool: `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration/r53_realistic_calibrated_val`
- QA summary: `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration/qa/r56_label_core_qa_summary.json`

## Planned Training

- Scratch run: 50 epochs, batch 16, 4 workers, PSF-forward loss disabled
- Boundary geometry: enabled from the repaired package sidecars
- Formal log pointer: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R56_LabelCoreRepairTraining/results/formal_training_logs/latest_formal_training_log.txt`

## Validation

- Real Lab checkboard reconstruction target: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare`
- Corner validation: completed and failed against Lab R40 / R55 best
- External GMF: not recommended from R56 because local real-corner validation failed

## Training Runs

- Formal run: `Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r56_label_core_repair_r53_scratch_formal_label_core_repair_e050_b016_w04_nophys_20260618_122705`
- Formal stdout: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R56_LabelCoreRepairTraining/results/formal_training_logs/r56_formal_label_core_repair_e050_b016_w04_nophys_20260618_122702_stdout.log`
- Formal stderr: `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R56_LabelCoreRepairTraining/results/formal_training_logs/r56_formal_label_core_repair_e050_b016_w04_nophys_20260618_122702_stderr.log`

## Reconstruction Runs

- Best tradeoff: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r56_label_core_repair_best_tradeoff`
- Latest: `Thesis_MOSR_Evidence/LabSystem_MOSR/Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r56_label_core_repair_latest`
- Corner validation report: `reports/R56_CHECKBOARD_VALIDATION.md`

## Verification

- `C:\Users\Rio\anaconda3\python.exe -m pytest Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R56_LabelCoreRepairTraining/tests -q`
- `C:\Users\Rio\anaconda3\python.exe Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R56_LabelCoreRepairTraining/scripts/launch_r56.py --candidate r56_label_core_repair_r53_scratch --data-root Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration --num-epoch 50 --dry-run`
- `C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R56_LabelCoreRepairTraining/scripts/run_r56_checkboard_reconstruction.py`
- `C:\Users\Rio\anaconda3\python.exe -u Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R56_LabelCoreRepairTraining/scripts/validate_r56_checkboard_corner_geometry.py`


## 2026-09-26 歷史封存狀態

完整 H 副本與 D 保留內容已逐檔核對；正式訓練成果、原報告及角點驗證留在 D。待清理原件仍在 D，回收 0 bytes。完整入口見 ARCHIVE_POINTER_R56_20260926.md；研究結論維持未採用。


## 2026-09-26 最新狀態：封存與 D 槽清理完成

4 個已核對的歷史目錄已透過使用者正式核准，以原生 PowerShell 移除。
H 槽完整歷史 39,499 檔在移除後再次逐檔核對，全部一致。
D 槽保留內容 23 檔及 62 個原成果／程式／驗證檔再次核對通過。
正式訓練成果及原報告留在原位置；研究判決沒有改變。
兩批合計的當下 D 可用空間增加約 25.6136 GiB，清理完成時約 376.935 GiB。
此為兩批合計量測，沒有單獨歸算每輪回收量。其他訓練持續執行，檔案標示容量與真正占用不同。

恢復時由 H 的 payload 按 LabSystem 相對路徑複製回原位置，再按 source_manifest.csv 核對。
要重做歷史訓練，需先恢復資料，或在啟動程式明確指定封存資料位置。
完整副本：H:\GMM_2_Final_Archive\lab_system\R56_LabelCoreRepairTraining\20260926_full_history
本次實際移除與核對：docs/operations/storage_execution_20260926/native_cleanup_execution.json、post_cleanup_verification.json。
