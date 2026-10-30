# Cleanup Report (2026-03-07)

## Goal
- normalize names
- keep only reproducible training artifacts
- separate current selected assets from rejected and historical assets

## Final Structure
- `Experiments/Legacy/auto_tune_logs`
  - empty runtime scratch directory kept for future autotune runs
- `Experiments/Legacy/auto_tune_reports`
  - empty runtime scratch directory kept for future autotune runs
- `Experiments/Legacy/organized_20260306/selected`
  - current adopted assets only
- `Experiments/Legacy/organized_20260306/rejected`
  - explicitly rejected autotune round artifacts
- `Experiments/Legacy/organized_20260306/archive`
  - older selected history and earlier reports

## Naming Rules Applied
- report files use `auto_tune_report_<timestamp>_<candidate>.json` when candidate identity is known
- console logs use `auto_tune_console_<timestamp>_<tag>.log`
- `selected/` contains only the current adopted 8px run and its logs/reports
- superseded adopted runs were moved out of `selected/` into `archive/`

## Current Selected Assets
- run:
  - `Experiments/Legacy/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332`
- checkpoint:
  - `Experiments/Legacy/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/weights/best_tradeoff.pth.tar`
- report:
  - `Experiments/Legacy/organized_20260306/selected/reports/auto_tune_report_20260306_190250_step8_curve_sharp_partial.json`
- logs:
  - `Experiments/Legacy/organized_20260306/selected/logs/auto_tune_console_20260306_190250_step8_full.out.log`
  - `Experiments/Legacy/organized_20260306/selected/logs/auto_tune_console_20260306_190250_step8_full.err.log`
  - `Experiments/Legacy/organized_20260306/selected/logs/auto_tune_console_20260306_190250_step8_full.meta.txt`

## Historical Assets Preserved
- archived previous adopted run:
  - `Experiments/Legacy/organized_20260306/archive/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_annulus_focus_boundary_20260306_155037`
- archived previous adopted report:
  - `Experiments/Legacy/organized_20260306/archive/reports/auto_tune_report_20260306_153531_annulus_focus_boundary.json`
- archived older shift-priority report:
  - `Experiments/Legacy/organized_20260306/archive/reports/auto_tune_report_20260306_115009_shift_priority.json`
- rejected baseline round:
  - `Experiments/Legacy/organized_20260306/rejected/reports/auto_tune_report_20260306_160824_baseline.json`

## Heavy Artifact Pruning
- removed sweep run folders from `Experiments/Legacy/`
- removed smoke-test logs
- removed duplicated top-level autotune reports/logs after archiving
- pruned the archived `annulus_focus_boundary` run to keep only:
  - `best_tradeoff.pth.tar`
  - `best_detail_guarded.pth.tar`
  - `*_ema_best_tradeoff.pth.tar`
  - `run_meta.json`
  - `monitor_ref.json`
  - monitor input/meta
  - csv/png/txt diagnostics needed for traceability
- pruned the current `step8_curve_sharp` run to keep only selected weights and required logs/metadata

## Size Summary
- total `Traing_Progress`: `~0.254 GB`
- `organized_20260306/selected`: `~0.101 GB`
- `organized_20260306/archive`: `~0.152 GB`
- `organized_20260306/rejected`: `~0.0005 GB`

## Compatibility Check
- current manual inference script still points to the selected 8px checkpoint:
  - `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
- selected checkpoint path remains valid after cleanup
- runtime scratch directories were intentionally kept, so future autotune runs can still use the old default output locations
