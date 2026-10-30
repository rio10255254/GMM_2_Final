# R56 Label-Core Repair Training

R56 trains the Lab model on the R56 label-core repaired version of the R53/R55
source-style package. The goal is to test whether sharpening only the weak label
core regions improves real Lab checkboard edge and corner reconstruction without
changing the broader R53/R55 data mix.

## Status

- Data package: prepared before this experiment
- Geometry sidecars: verified from the repaired package manifest
- Training launcher: `scripts/launch_r56.py`
- Smoke training: launcher tests and dry-run passed
- Formal training: completed as a 50-epoch scratch run, batch 16, 4 workers, PSF-forward loss disabled
- Real checkboard validation: failed; R56 best matched R55 best median shift but had a worse tail and worse large-shift rate

## Training Data Plan

The first formal run uses the repaired 6000-pair R53-style core package only:

- Train package: `LabSystem_MOSR/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration/r53_realistic_calibrated_train_6000`
- Held-out repaired package for later visual checks: `LabSystem_MOSR/Training_Data/r56_label_core_repair/r53_realistic_dataset_calibration/r53_realistic_calibrated_val`

The larger expansion pools are not mixed into this run so the comparison against
R55 stays readable.

## Active Training

- Log pointer: `results/formal_training_logs/latest_formal_training_log.txt`
- Training root: `LabSystem_MOSR/Traing_Progress`
- Current run: `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r56_label_core_repair_r53_scratch_formal_label_core_repair_e050_b016_w04_nophys_20260618_122705`

## Current Result

R56 is complete but not usable as the next Lab candidate. Internal validation
kept improving through epoch 50 (`PSNR 26.40`, `SSIM 0.9333`), but the real
Lab checkboard corner gate failed. R56 best_tradeoff reached the same median
corner shift as R55 best (`2.828 px`) but worsened large-shift corners
(`26.816%` vs R55 `21.788%`) and tail shift (`9.899 px` vs R55 `3.606 px`).
R56 latest failed badly (`9.899 px` median / `59.777%` >5 px corners).

## Formal Run Command

```powershell
C:\Users\Rio\anaconda3\python.exe -u .\LabSystem_MOSR\Experiments\R56_LabelCoreRepairTraining\scripts\launch_r56.py `
  --candidate r56_label_core_repair_r53_scratch `
  --data-root .\LabSystem_MOSR\Training_Data\r56_label_core_repair\r53_realistic_dataset_calibration `
  --num-epoch 50 `
  --batch-size 16 `
  --val-batch-size 4 `
  --num-workers 4 `
  --seq-batch-size 4 `
  --run-suffix formal_label_core_repair_e050_b016_w04_nophys
```


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
