# 自動調優持續報告 (2026-03-06)

> 歷史紀錄：本報告對應的是舊版 `annulus_focus_boundary` 採用結果，後續已被 `step8_curve_sharp` 取代。相關產物現已歸檔到 `archive/`。

## 目標
- 主要：邊界位置重建準確度和微小位移敏感度（GMF/PM 下游穩定性）。
- 次要：邊界銳利度和真實紋理恢復。

## 已套用的變更
- `Training_Data/PSF_Convolution.py`
  - `PHOTON_SCALE_RANGE`: `(30.0, 150.0)` -> `(45.0, 180.0)`
  - `READ_NOISE_SIGMA_RANGE`: `(0.8, 3.0)` -> `(0.7, 2.2)`
- `Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py`
  - 為短時間掃描（sweep）添加了穩健的最佳 epoch 回退機制。
  - 添加/更新了具有環帶聚焦（annulus-focused）訓練選項的候選配置。
  - 將第一輪（較好的）微小位移混合設定保留為最終腳本狀態。
- `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py`
  - 將 `MANUAL_WEIGHTS_PATH` 更新為所選執行的權重。

## 自動化執行

### 執行 A (已採用)
- 報告：`Traing_Progress/organized_20260306/archive/reports/auto_tune_report_20260306_153531_annulus_focus_boundary.json`
- 設定：`sweep=12`, `final=50`
- 最佳候選：`annulus_focus_boundary`
- 最終執行目錄：
  - `Traing_Progress/organized_20260306/archive/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_annulus_focus_boundary_20260306_155037`
- 最終摘要：
  - `best_step_err = 22.2390`
  - `best_pos_std_sum = 22.2390`
  - `best_pass02_estimate = 0.5833`
  - `best_edge_width = 7.0646`
  - `best_hf_proxy = 1.6264e-05`

### 執行 B (已拒絕)
- 報告：`Traing_Progress/organized_20260306/rejected/reports/auto_tune_report_20260306_160824_baseline.json`
- 設定：`sweep=10`, `final=40`
- 結果相較於執行 A 有所退步：
  - `best_step_err = 26.6868`
  - `best_pos_std_sum = 26.6868`
  - `best_pass02_estimate = 0.4375`
  - `best_edge_width = 9.3699`
- 決策：拒絕。

## 最終採用的權重
- 主要：
  - `Traing_Progress/organized_20260306/archive/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_annulus_focus_boundary_20260306_155037/weights/best_tradeoff.pth.tar`
- 替代方案：
  - `.../weights/best_detail_guarded.pth.tar`
  - `.../weights/GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_annulus_focus_boundary_ema_best_tradeoff.pth.tar`

## 備註
- 手動訓練/推論腳本在這些更新後編譯成功。
- 本報告對應的舊版權重已歸檔保存，但目前推論手動路徑預設已改指向 `step8_curve_sharp` 的 `best_tradeoff.pth.tar`。
