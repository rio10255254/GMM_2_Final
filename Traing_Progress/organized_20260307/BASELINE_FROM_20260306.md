# 20260307 測試基準版

## 基準目的

這份文件用來固定 `20260307` 後續所有測試的比較基準。

目前基準版來源：
- `Traing_Progress/organized_20260306/selected/`

## 基準 run

- `Traing_Progress/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332`

## 基準權重

- `Traing_Progress/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/weights/best_tradeoff.pth.tar`

## 基準報告

- `Traing_Progress/organized_20260306/AUTO_TUNE_8PX_REPORT_20260306.md`

## 基準評估方向

後續任何新版本，都至少要和這份基準版比較以下項目：

1. `POSY` 步長平均值是否仍接近 `8 px`
2. `POSY` 步長標準差是否更低
3. `P05-P95 span` 是否更窄
4. 邊界是否更真實、更銳利，但不能以犧牲定位穩定性為代價

## 判定原則

- 如果新版本讓步長標準差下降，而且均值沒有明顯偏離 `8 px`，就有升級價值
- 如果新版本只是看起來更銳利，但 `POSY` 步長標準差上升，則不採用
