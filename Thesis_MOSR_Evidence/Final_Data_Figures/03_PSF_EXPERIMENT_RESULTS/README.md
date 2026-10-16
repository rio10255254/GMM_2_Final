# PSF Experiment Results and Analysis

這個資料夾收集論文中 PSF 實驗結果與分析會用到的乾淨材料。

論文中可以把這一段串成三步：

1. 先說明用 BADS 做全視野 PSF 擬合，得到後續模型可使用的位置相關 PSF。
2. 接著用敏感度分析確認哪些參數真的會改變 PSF 形狀，哪些參數不適合過度解讀。
3. 最後用重複擬合、跨次拍攝與影像層級檢查，說明擬合結果不是單次偶然結果。

資料夾分工：

- `01_global_bads_fit`：全視野 BADS 擬合的主要圖、表、完整來源資料與文字摘要。
- `02_sensitivity_analysis`：PSF 參數敏感度與 SAF 敏感度分析，適合放在方法驗證或補充分析。
- `03_fit_validation`：擬合結果驗證，包括 L0/L1 重複性與 paired-frame 檢查。

優先使用材料：

- 全視野擬合圖：`psf_montage_log_normalized.png`、`fval_heatmap.png`、`psf_representative_comparison.png`。
- 敏感度分析圖：`parameter_shape_sensitivity_rank.png`、`best_fit_shape_response_rank.png`、`best_fit_loss_saf_rank.png`。
- 驗證分析圖：`chart_02_l0_noise_floor_by_round.png`、`chart_03_l1_capture_vs_l0_floor_by_fov.png`、`chart_06_paired_frame_edge_diff_heatmap.png`。

今天重新執行並整理的紀錄在 `execution_summary_20260707.md`。
