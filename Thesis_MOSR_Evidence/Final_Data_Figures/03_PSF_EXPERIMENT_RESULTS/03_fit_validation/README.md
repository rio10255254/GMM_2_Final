# Fit Validation

這裡放的是「擬合結果是否穩定、是否能作為後續模型資料」的驗證材料。

建議論文使用方式：

- `figures/chart_02_l0_noise_floor_by_round.png`：看重複擬合本身的基本波動範圍。
- `figures/chart_03_l1_capture_vs_l0_floor_by_fov.png`：比較跨次拍攝變化是否落在重複擬合可接受範圍內。
- `figures/chart_06_paired_frame_edge_diff_heatmap.png`：從影像層級檢查 paired-frame 的邊緣差異分布。
- `figures/chart_08_paired_frame_distribution_by_round.png`：看 paired-frame 差異在不同輪次的分布。
- `tables/paired_frame_metrics.csv`：paired-frame 每個位置的數值結果。
- `notes/L0_newdata_summary.md`、`notes/L1_newdata_summary.md`：L0/L1 驗證摘要。
- `notes/paired_frame_summary.md`：paired-frame 驗證摘要。

目前結果的讀法：

- L1 跨次拍攝差異低於 L0 重複擬合底線，適合支撐「PSF 擬合結果具備可重複性」。
- paired-frame 檢查可以作為影像層級的輔助驗證，但不要把它寫成唯一真值標準。
- 這一段最適合放在「擬合結果驗證」或「資料可靠性」段落。
