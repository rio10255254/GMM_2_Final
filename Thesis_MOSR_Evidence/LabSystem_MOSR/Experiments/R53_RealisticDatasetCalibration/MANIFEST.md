# R53 Realistic Dataset Calibration Manifest

## Experiment

- ID: R53_RealisticDatasetCalibration
- Status: completed; real checkboard gate failed; not promoted
- Created: 2026-06-16
- Scope: LabSystem_MOSR only; not a main-project baseline challenger

## Source Scripts

- `scripts/r53_realistic_dataset_data.py`
- `scripts/launch_r53.py`
- `scripts/start_r53_formal_training.ps1`
- `scripts/run_r53_checkboard_reconstruction.py`
- `scripts/r53_corner_gate.py`

## Data Packages

- Train: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r53_realistic_dataset_calibration\r53_realistic_calibrated_train_6000`
- Validation: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r53_realistic_dataset_calibration\r53_realistic_calibrated_val`

## Training Runs

- Smoke batch 16: `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r53_realistic_calibrated_scratch_smoke_e001_b002_20260616_141409`
- Probe batch 32: `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r53_realistic_calibrated_scratch_probe_b032_20260616_141514`
- Probe batch 48: failed with CUDA out of memory
- Formal batch 32 / workers 8: failed at epoch 2 validation worker startup with Windows-side `MemoryError`
- Formal batch 32 / workers 4 / PSF-forward loss on: reached epoch 11, then became unacceptably slow when PSF-forward loss activated
- Stability test batch 32 / workers 4 / PSF-forward loss off: `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r53_realistic_calibrated_scratch_stability_e012_b002_w04_nophys_20260616_152118`
- Formal batch 32 / workers 4 / PSF-forward loss off: reached epoch 11, then failed with CUDA out of memory when shift equivariance activated
- Completed formal batch 16 / workers 4 / PSF-forward loss off: `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r53_realistic_calibrated_scratch_formal_b016_w04_nophys_e100_20260616_154939`

## Reports And Results

- Initial report: `reports/R53_RESULTS.md`
- Real checkboard validation report: `reports/R53_CHECKBOARD_VALIDATION.md`
- Best checkpoint corner gate: `results/r53_best_tradeoff_corner_gate.json`
- Latest checkpoint corner gate: `results/r53_latest_corner_gate.json`
- Dataset audit JSON: `results/dataset_audit/r53_dataset_audit.json`
- Dataset contact sheet: `results/dataset_audit/r53_train_contact_sheet.png`
- Formal log pointer: `results/formal_training_logs/latest_formal_training_log.txt`
- R53 reconstruction outputs: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\r53_reconstruction_outputs`
- R53 corner validation artifacts: `D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\corner_geometry_validation_r53_20260616`

## Verification

- `C:\Users\Rio\anaconda3\python.exe -m pytest D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R53_RealisticDatasetCalibration\tests -q`
- `C:\Users\Rio\anaconda3\python.exe LabSystem_MOSR\Experiments\R53_RealisticDatasetCalibration\scripts\r53_realistic_dataset_data.py validate-splits --profile all`
- `C:\Users\Rio\anaconda3\python.exe LabSystem_MOSR\Experiments\R53_RealisticDatasetCalibration\scripts\launch_r53.py --candidate r53_realistic_calibrated_scratch --num-epoch 100 --dry-run`
- `C:\Users\Rio\anaconda3\python.exe -u LabSystem_MOSR\Experiments\R53_RealisticDatasetCalibration\scripts\launch_r53.py --candidate r53_realistic_calibrated_scratch --num-epoch 2 --batch-size 32 --val-batch-size 8 --num-workers 4 --max-train-batches 2 --val-ratio 0.01 --run-suffix stability_e002_b002_w04`
- `C:\Users\Rio\anaconda3\python.exe -u LabSystem_MOSR\Experiments\R53_RealisticDatasetCalibration\scripts\run_r53_checkboard_reconstruction.py --checkpoint-kind both --device cuda:0`
- `C:\Users\Rio\anaconda3\python.exe -u LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\validate_checkboard_corner_geometry_r53.py`


## 2026-09-26 完整歷史封存

19 個來源、39,661 個檔案（18.7058 GiB）已完整保存在 H:/GMM_2_Final_Archive/lab_system/R53_RealisticDatasetCalibration/20260926_full_history，逐檔 SHA-256 一致。D 保留包 121 檔已核對；原啟動程式能由 H 資料讀到 6,000 組配對。D 清理被執行工具拒絕，原件仍在，回收 0 bytes。詳見 ARCHIVE_POINTER_R53_20260926.md；未改變本輪未採用的判決。


## 2026-09-26 最新狀態：封存與 D 槽清理完成

15 個已核對的歷史目錄已透過使用者正式核准，以原生 PowerShell 移除。
H 槽完整歷史 39,661 檔在移除後再次逐檔核對，全部一致。
D 槽保留內容 121 檔及 104 個原成果／程式／驗證檔再次核對通過。
正式訓練成果及原報告留在原位置；研究判決沒有改變。
兩批合計的當下 D 可用空間增加約 25.6136 GiB，清理完成時約 376.935 GiB。
此為兩批合計量測，沒有單獨歸算每輪回收量。其他訓練持續執行，檔案標示容量與真正占用不同。

恢復時由 H 的 payload 按 LabSystem 相對路徑複製回原位置，再按 source_manifest.csv 核對。
要重做歷史訓練，需先恢復資料，或在啟動程式明確指定封存資料位置。
完整副本：H:\GMM_2_Final_Archive\lab_system\R53_RealisticDatasetCalibration\20260926_full_history
本次實際移除與核對：D:/GMM_2_Final/docs/operations/storage_execution_20260926/native_cleanup_execution.json、post_cleanup_verification.json。
