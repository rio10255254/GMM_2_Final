# R53 Realistic Dataset Calibration

R53 rebuilds the Lab-system training package after R52 failed the real-corner
stability gate. The purpose is to stop over-focusing on checkboard corners and
return the Lab package toward the main-project data mix: rings, shape
generalization, microscopy detail, realistic gray backgrounds, mixed-PSF
corners, and masked real CAD checkboard anchors.

## Status

- Data package: built
- Unit tests: passed
- Visual data audit: completed
- Smoke training: passed at batch 16 and batch 32
- Batch probe: batch 48 failed CUDA memory; batch 16 was the final formal run setting
- Formal training: completed from scratch, 100 epochs, batch 16, 4 workers, PSF-forward loss disabled
- Real checkboard validation: failed; R53 is not promoted

## Main Artifacts

- Data builder: `scripts/r53_realistic_dataset_data.py`
- Training launcher: `scripts/launch_r53.py`
- Formal training starter: `scripts/start_r53_formal_training.ps1`
- Checkboard reconstruction runner: `scripts/run_r53_checkboard_reconstruction.py`
- Real-corner gate: `scripts/r53_corner_gate.py`
- Training package: `LabSystem_MOSR/Training_Data/r53_realistic_dataset_calibration/r53_realistic_calibrated_train_6000`
- Validation package: `LabSystem_MOSR/Training_Data/r53_realistic_dataset_calibration/r53_realistic_calibrated_val`
- Visual audit: `results/dataset_audit/r53_train_contact_sheet.png`
- Formal training log pointer: `results/formal_training_logs/latest_formal_training_log.txt`
- Real checkboard validation: `reports/R53_CHECKBOARD_VALIDATION.md`

## Train Package Mix

| Role | Count |
|---|---:|
| ring | 700 |
| shape | 700 |
| micro/detail | 900 |
| mixed-PSF corner | 300 |
| realistic boundary | 2050 |
| real background / real texture | 950 |
| masked CAD anchor | 400 |
| total | 6000 |

The mixed-PSF corner subset is evenly split across formal BADS, Gaussian, and
weak-BADS alpha 0.50 sources. CAD anchor labels keep the source image outside
the reliable mask, so partial CAD GT does not force the full image.

## Formal Run Command

```powershell
C:\Users\Rio\anaconda3\python.exe -u .\LabSystem_MOSR\Experiments\R53_RealisticDatasetCalibration\scripts\launch_r53.py `
  --candidate r53_realistic_calibrated_scratch `
  --num-epoch 100 `
  --batch-size 16 `
  --val-batch-size 4 `
  --num-workers 4 `
  --seq-batch-size 4 `
  --run-suffix formal_b016_w04_nophys_e100
```

The earlier worker-8 formal attempt reached epoch 2 but failed during the
validation/worker stage with a Windows-side `MemoryError`. R53 now uses 4
workers with non-persistent data-loader workers to avoid that overlap.

The first worker-4 formal attempt then became unacceptably slow at epoch 11
when the PSF-forward loss first became active. The completed long run kept the
Lab PSF file configured but disabled that extra PSF-forward loss so training
could complete.

The batch-32 no-PSF-forward attempt then failed at epoch 11 when shift
equivariance added a second model forward. The completed run used batch 16 to
keep that training signal instead of disabling it.

## Final Result

The batch-16 formal run completed 100 epochs. Internal validation continued to
improve through epoch 100, but real Lab checkboard validation failed:

| Case | Median corner shift (px) | Corners > 5 px shift |
|---|---:|---:|
| Lab R40 tradeoff | 4.243 | 24.581% |
| Lab R52 latest | 3.606 | 30.447% |
| R53 best_tradeoff | 3.606 | 40.782% |
| R53 latest | 9.220 | 58.939% |

R53 therefore remains failure evidence for the Lab transfer line, not a usable
Lab baseline.


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
