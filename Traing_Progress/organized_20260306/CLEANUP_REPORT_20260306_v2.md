# Cleanup Report v2 (2026-03-06)

> Historical snapshot: this report was superseded by the final structure recorded in `CLEANUP_REPORT_20260307.md`.

## Scope
- Request: carefully archive and clean training artifacts, remove unused training records.
- Time: 2026-03-06 (local).

## Actions
- Kept only two top-level folders in `Traing_Progress/`:
  - `auto_tune_reports`
  - `organized_20260306`
- Moved adopted run into organized selected path:
  - `organized_20260306/archive/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_annulus_focus_boundary_20260306_155037`
- Removed unused heavy run folders:
  - all remaining top-level `training_progress_*`
  - `organized_20260306/archive/runs`
  - old selected run `...AUTO_FINAL_shift_priority_20260306_120501`
- Preserved report/log traceability:
  - adopted report/log copied to `organized_20260306/selected/reports` and `organized_20260306/selected/logs`
  - rejected round report/log copied to `organized_20260306/rejected/reports` and `organized_20260306/rejected/logs`

## Space Summary
- Estimated removable before cleanup:
  - top-level unused runs: `19.904 GB`
  - old selected run: `1.005 GB`
  - archive runs: `7.607 GB`
  - total: `28.516 GB`
- After cleanup:
  - `organized_20260306`: `~1.01 GB`
  - `auto_tune_reports`: `~0.00 GB`

## Path Sync
- Updated inference manual weight pointer to the new archived selected location:
  - `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
