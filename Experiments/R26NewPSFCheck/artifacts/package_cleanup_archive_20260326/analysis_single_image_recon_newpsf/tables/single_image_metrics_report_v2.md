# 單張重建總表 v2

|image|CNR_main|CNR_weak|HF_ratio|background_grad_p95|background_std|checkerboard_ratio|edge_continuity_ratio|edge_width_main_px|edge_width_weak_px|max_slope_main|max_slope_weak|ring_thickness_std_px|
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|RAW|6.9773|9.0287|0.6185|24.2074|2.9010|0.1447|0.4861|43.5622|51.2560|2.6301|1.8971|5.5552|
|R26|9.1935|7.7921|0.0164|3.1623|1.0903|0.2148|0.2667|36.2600|49.0800|4.3940|2.0769|1.5523|

## 結果解讀重點
1. 邊界集中化仍是主證據，但改善幅度有限。相較於 RAW，`edge_width_main_px` 與 `edge_width_weak_px` 皆下降，`max_slope_main` 與 `max_slope_weak` 皆上升，表示邊界轉換仍有集中化；但弱邊界改善幅度較小，不宜寫成大幅提升。
2. 對比改善不具一致性，必須結合背景抑噪一起解讀。`CNR_main` 由 `6.9773` 升至 `9.1935`，但 `CNR_weak` 由 `9.0287` 降至 `7.7921`。因此不能把結果寫成整體局部對比全面提升；較合理的解讀是主邊界受益於邊界集中化，加上 `background_std` 與 `background_grad_p95` 顯著下降，但弱邊界對比並未同步改善。
3. 頻域只能作為保守的輔助資訊。`HF_ratio` 在本流程中定義為固定頻帶 `r=0.35–0.60` 的能量比，較接近固定高頻帶/噪聲帶能量佔比，不宜直接解讀成有效細節量。雖然 `HF_ratio` 顯著下降，顯示固定高頻帶能量受抑，但 `checkerboard_ratio` 由 `0.1447` 升至 `0.2148`，因此不能把頻域結果寫成高頻品質全面更好。
4. 幾何 proxy 呈現混合訊號。`ring_thickness_std_px` 由 `5.5552` 降至 `1.5523`，顯示環厚度分布更一致；但 `edge_continuity_ratio` 由 `0.4861` 降至 `0.2667`，在目前 threshold 與 edge rule 下反而變差。故幾何 proxy 只能保守解讀，且應以 `ring_thickness_std_px` 為主要參考，不宜用 `edge_continuity_ratio` 當 headline。
