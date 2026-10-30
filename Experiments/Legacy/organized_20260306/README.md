# 訓練產物總索引（中文）

> 目前狀態：`organized_20260306/` 已視為凍結基準版。後續新的自動化測試、重建輸出與 GMF 外部評估結果，請改收納到 `organized_20260307/`。

## 這份索引的用途
這份文件是目前 `Experiments/Legacy/organized_20260306/` 的單一入口。

目的只有三個：
- 讓你快速找到目前真正採用的權重與 run
- 讓你分清楚哪些是現行版本、哪些只是歷史紀錄
- 讓你之後手動推理或回頭查報告時，不會誤用舊資料夾

## 目前真正採用的版本

目前採用的是 `step8_curve_sharp` 這一輪。

- 採用 run：
  - `Experiments/Legacy/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332`
- 採用權重：
  - `Experiments/Legacy/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/weights/best_tradeoff.pth.tar`
- 採用報告：
  - `Experiments/Legacy/organized_20260306/AUTO_TUNE_8PX_REPORT_20260306.md`
- 採用 round 的自動化摘要：
  - `Experiments/Legacy/organized_20260306/selected/reports/auto_tune_report_20260306_190250_step8_curve_sharp_partial.json`

## 手動推理現在會用哪個權重

目前推理腳本已經預設指向上面這個採用權重，不需要另外修改即可直接使用。

對應程式：
- `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`

目前預設路徑是：

```text
Experiments/Legacy/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/weights/best_tradeoff.pth.tar
```

如果你未來要改成其他權重，直接修改 `MANUAL_WEIGHTS_PATH` 即可。

## 目錄怎麼看

### `selected/`
這裡只放「目前有效、目前採用」的東西。

- `runs/`
  - 目前採用的完整 run
- `reports/`
  - 目前採用 round 對應的報告
- `logs/`
  - 目前採用 round 的 console log / meta / err

你現在手動測試、手動推理、要找最終權重時，只需要先看這裡。

### `rejected/`
這裡放「有實際跑過，但最後明確不採用」的 round。

用途：
- 回頭對照為什麼某個策略被否決
- 查指標退化原因

這裡的檔案不應該再拿來當目前手動推理的預設來源。

### `archive/`
這裡放「曾經重要，但現在已不是現行採用版本」的歷史紀錄。

包含：
- 舊採用版 run
- 舊採用版報告
- 更早期的 autotune 報告

這裡的東西保留是為了可追溯性，不是為了現在直接拿來用。

## 歷史版本位置

### 舊採用版：`annulus_focus_boundary`
- 歸檔 run：
  - `Experiments/Legacy/organized_20260306/archive/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_annulus_focus_boundary_20260306_155037`
- 歸檔報告：
  - `Experiments/Legacy/organized_20260306/archive/reports/auto_tune_report_20260306_153531_annulus_focus_boundary.json`
- 說明文件：
  - `Experiments/Legacy/organized_20260306/AUTO_TUNE_CONTINUE_REPORT_20260306.md`

注意：這一版已經不是現在的預設採用版，只保留作歷史比較。

## 目前保留了哪些檔案，哪些已被清掉

### 目前保留
- 採用版的 `best_tradeoff.pth.tar`
- 歷史版必要的最佳權重
- `run_meta.json`
- `monitor_ref.json`
- 必要的 `csv/png/txt` 紀錄
- 採用與拒絕 round 的對應報告與 log

### 已清除
- 大量中間 `epoch_*.pth.tar`
- 大量 `monitor_epoch_*.bmp`
- 未採用的 sweep run 資料夾
- 重複或已失效的頂層 log / report
- 重複的 `latest.pth.tar` / 非必要輸出

整理原則很簡單：
- 保留可重現與可追溯所需的最小集合
- 刪掉不再需要的重型中間產物

## 你之後該先看哪幾個檔案

如果你現在是要直接做手動重建或定位測試，請先看這幾個：

1. `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
2. `Experiments/Legacy/organized_20260306/selected/runs/...step8_curve_sharp.../weights/best_tradeoff.pth.tar`
3. `Experiments/Legacy/organized_20260306/AUTO_TUNE_8PX_REPORT_20260306.md`

如果你是要回頭理解歷史版本差異，再看：

1. `Experiments/Legacy/organized_20260306/archive/`
2. `Experiments/Legacy/organized_20260306/rejected/`
3. `Experiments/Legacy/organized_20260306/CLEANUP_REPORT_20260307.md`

## 補充

- `Experiments/Legacy/auto_tune_logs/` 與 `Experiments/Legacy/auto_tune_reports/` 目前刻意保留為空資料夾，供未來自動化執行沿用。
- 目前整理後的結構，是以「手動使用方便、歷史追蹤清楚、命名規則一致」為主要原則。
