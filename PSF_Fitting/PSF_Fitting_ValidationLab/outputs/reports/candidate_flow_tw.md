# 正式候選流程說明

- 候選主程式：`PSF_Fitting/PSF_Fitting_ValidationLab/scripts/HDR_fitting_2D_WholeFOV_candidate_prealign.m`
- 這個候選版仍以原 Whole-FOV 流程的 loss、warm-start、BADS 參數與 PSF 重建方式為基底。
- 和原流程相比，主要新增的是顯式 `pre_alignment on/off` 開關、可設定 `prealign_step`，以及可指定 `subset_indices` / `output_root` 的獨立重跑能力。
- 目前候選版預設維持 `warm_start = true`。
- 目前候選版預設維持 `lock_tilt = true`。
- 目前候選版預設使用 `prealign_step = 0.5`，也就是 refined pre_alignment。
- `alignment_subpixel_rep16` 已把 mean abs peak offset 從 `baseline_rep16` 的 1.938 px 降到 0.562 px。
- 相比整數版 `alignment_rep16`，`alignment_subpixel_rep16` 把 mean peak offset_x 從 -0.812 壓到 -0.438，mean fval 從 1486.104 降到 1457.065。
- 目前仍不建議先把 tilt 放進正式主線：`alignment_tilt_rep16` 的 mean abs peak offset = 0.812 px，沒有優於 `alignment_subpixel_rep16` 的 0.562 px，且 mean iterations 多 16.2。
- 因此目前最值得收斂成正式版的機制是：`warm_start + refined pre_alignment + tilt locked`。
- 候選主程式輸出仍維持與原流程相近的 `batch_results.csv` 與 `PSF_fitted_2D_FOVstack.mat`。
- 已用 1 張圖的 smoke run 實際跑成功，證明 candidate 主程式可用。
