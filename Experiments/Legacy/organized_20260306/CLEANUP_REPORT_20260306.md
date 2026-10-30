# 清理報告 (2026-03-06)

> 歷史紀錄：這是 2026-03-06 首輪整理的快照，部分路徑已被後續整理取代。請以 `CLEANUP_REPORT_20260307.md` 為目前有效結構。

## 範圍
本次清理針對 2026-03-06 期間長達數小時的自動化執行所產生的產出物。

## 保留項目 (精選)
- 執行資料夾：
  - `已於後續整理中移除；僅保留對應歷史報告`
- 報告：
  - `Experiments/Legacy/organized_20260306/archive/reports/auto_tune_report_20260306_115009_shift_priority.json`

## 已封存
- 已封存的執行資料夾：`19`
  - 位置：`Experiments/Legacy/organized_20260306/archive/runs/`
- 已封存的報告：`4`
  - 位置：`Experiments/Legacy/organized_20260306/archive/reports/`

## 已移除
- 失敗的快速測試資料夾（輸出為空或不完整）：
  - `Experiments/Training_Runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_QUICK_NO_PHYS_20260306_122548`
- 重新定位後空的報告目錄：
  - `Experiments/Legacy/auto_tune_reports`

## 運行時相容性檢查 (手動模式)
使用目前的腳本版本從當前工作區進行檢查：

- 語法編譯通過：
  - `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`
  - `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
  - `Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py`
- CLI 幫助調用通過：
  - `python GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py --help`
  - `python GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py --help`

結果：訓練和推論進入點在手動模式下可正常調用，且 CLI 行為風格與之前一致。

## 採用的腳本版本
目前保留/採用的版本為 `Model/` 中的現有檔案：
- `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`
- `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
- `Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py`

這些是上述精選保留的執行/報告所使用的版本。
