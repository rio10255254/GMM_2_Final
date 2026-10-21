# R45 產物清單

## 文件

- `README.md`：實驗目的與結論摘要。
- `MANIFEST.md`：本清單。
- `reports/R45_RESULTS.md`：R45 canonical 結果報告。
- `reports/R45B_TEACHER_DIAGNOSTICS.md`：R45B 老師殘差與理想分族診斷報告。

## 腳本

- `scripts/r45_adapter_model.py`：凍結主模型與分族小校正模組。
- `scripts/r45_adapter_data.py`：R45 目標資料讀取。
- `scripts/train_r45_adapter.py`：小校正模組訓練。
- `scripts/run_r45_adapter_recon.py`：單一入口重建流程。
- `scripts/r45_adapter_metrics.py`：R45 與 R44B from R42 的比較評分。
- `scripts/r45b_teacher_diagnostics.py`：R45B 老師殘差、oracle 上限與可轉移性診斷。

## 測試

- `tests/test_r45_adapter_model.py`：確認主模型凍結、非目標類型不被改動、checkpoint 可讀寫。
- `tests/test_r45_adapter_data.py`：確認目標 stage 與 manifest 讀取。
- `tests/test_r45_adapter_metrics.py`：確認門檻判定邏輯。

## 主要結果

- `results/checkpoints/r45_oracle_adapter_large_mixed.pth`：正式短訓練小模組。
- `results/checkpoints/r45_oracle_adapter_large_mixed_s04.pth`：校正強度 0.04 掃描版本。
- `results/checkpoints/r45_oracle_adapter_large_mixed_s08.pth`：校正強度 0.08 掃描版本。
- `results/checkpoints/r45_oracle_adapter_large_mixed_s12.pth`：校正強度 0.12 掃描版本。
- `results/diagnostics/r45_adapter_scale_sweep_summary.csv`：縮放掃描總表。
- `results/diagnostics/r45_adapter_scale_sweep_summary.json`：縮放掃描機器可讀總表。
- `results/diagnostics/r45_oracle_adapter_large_mixed*_metrics.json`：各版本完整比較結果。
- `results/motion_recon/`：各版本在 R44 motion_val_unseen 的完整重建輸出。
- `results/visual_samples/r45_s08_vs_r44b_target_compare.png`：代表圖比較。
- `results/r45b_teacher_diagnostics/r45b_oracle_summary.json`：R45B oracle 與老師可轉移性總結。
- `results/r45b_teacher_diagnostics/r45b_target_rank.csv`：大區塊/混合場景總排名。
- `results/r45b_teacher_diagnostics/r45b_residual_summary.csv`：老師殘差方向統計。
- `results/visual_samples/r45b_teacher_diagnostics_sheet.png`：R45B 老師比較代表圖。

## 驗證命令

- `python -m pytest Experiments\R45_FamilyBoundaryAdapter\tests -q`
- `python Experiments\R45_FamilyBoundaryAdapter\scripts\train_r45_adapter.py --epochs 1 --batch-size 1 --max-pairs-per-stage 2 --crop-size 128 --device cuda:0 --output Experiments\R45_FamilyBoundaryAdapter\results\checkpoints\r45_smoke_adapter.pth`
- `python Experiments\R45_FamilyBoundaryAdapter\scripts\run_r45_adapter_recon.py --adapter-checkpoint Experiments\R45_FamilyBoundaryAdapter\results\checkpoints\r45_oracle_adapter_large_mixed_s08.pth --tag r45_oracle_adapter_large_mixed_s08 --device cuda:0`
- `python Experiments\R45_FamilyBoundaryAdapter\scripts\r45_adapter_metrics.py --tag r45_oracle_adapter_large_mixed_s08`
- `python Experiments\R45_FamilyBoundaryAdapter\scripts\r45b_teacher_diagnostics.py`
