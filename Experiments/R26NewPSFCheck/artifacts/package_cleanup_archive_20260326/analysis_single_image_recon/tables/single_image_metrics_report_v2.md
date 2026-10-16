# 單張重建總表 v2

|image|CNR_main|CNR_weak|HF_ratio|background_grad_p95|background_std|checkerboard_ratio|edge_continuity_ratio|edge_width_main_px|edge_width_weak_px|max_slope_main|max_slope_weak|ring_thickness_std_px|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|RAW|6.9773|9.0287|0.6185|24.2074|2.9010|0.1447|0.4861|43.5622|51.2560|2.6301|1.8971|5.5552|
|R26|19.5539|33.3378|0.0103|3.1623|0.6529|0.1208|0.9944|33.4741|34.0101|6.4505|5.2905|4.2530|

## 結果解讀重點
1. 邊界集中化是主證據。`edge_width_main_px`、`edge_width_weak_px` 明顯下降，且 `max_slope_main`、`max_slope_weak` 明顯上升，這是本報告最核心、最穩定的主結論。
2. CNR 提升需結合背景抑噪一起解讀。`CNR_main` 與 `CNR_weak` 的上升，不應單獨寫成結構訊號變強；更合理的解讀是邊界集中化，加上 `background_std` 與 `background_grad_p95` 顯著下降，表示局部對比改善來自邊界集中與背景抑噪的共同作用。
3. 頻域主要用來排除假高頻與說明頻帶集中。`HF_ratio` 在本流程中定義為固定頻帶 `r=0.35–0.60` 的能量比，較接近固定高頻帶/噪聲帶能量佔比，不宜直接解讀成有效細節量；`checkerboard_ratio` 未上升，因此頻域結果主要作為未見明顯假高頻副作用的輔助證據。
4. 幾何 proxy 僅保守支持應用價值。`ring_thickness_std_px` 應作為較穩健的主幾何 proxy；`edge_continuity_ratio` 受 threshold 與 edge rule 影響較大，應降為輔助支持，不宜作為 headline 指標。