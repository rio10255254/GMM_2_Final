# 下一步建議

- 先以 `alignment_quarter_rep16` 當作正式修正版候選。
- 目前證據支持先保留 warm-start，並把 pre_alignment 變成正式流程的顯式選項。
- 這輪最有價值的收斂點是 `alignment_quarter_rep16` 的 `prealign_step = 0.25`；它同時改善 offset 與 fval，應直接進入候選主程式預設。
- `alignment_tilt_rep16` 目前不值得進正式主線：它的 mean abs peak offset 為 0.812 px，沒有優於 `alignment_quarter_rep16` 的 0.500 px，且 mean iterations 多 0.8。
- 若之後要重新評估 tilt，建議只在 refined pre_alignment 已開啟的前提下再測，避免把兩個問題混在一起。
- 若 MATLAB run 被中斷，只要各實驗資料夾中的 `batch_results.csv` 已存在，就可直接重跑聚合，不需要重跑 fitting。
