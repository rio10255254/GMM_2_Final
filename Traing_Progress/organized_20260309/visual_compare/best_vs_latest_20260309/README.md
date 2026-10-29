# 視覺重建比較結果

本次只做 3 張代表樣本的小規模比較，使用 CPU 執行，不影響正在進行中的背景訓練。

比較權重：
- 目前最佳基準權重：Traing_Progress/organized_20260307/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar
- 最新穩定權重：Traing_Progress/training_progress_GESR_v1_v5_ST0p08_SWP_mcf_20260309_231113/weights/best_tradeoff.pth.tar
- 說明：目前仍在進行中的 mdb 權重沒有拿來做這次比較，因為它仍可能正在寫入 checkpoint。

- 輸入樣本：Traing_Progress/organized_20260309/visual_compare/best_vs_latest_20260309/input_samples
- 基準權重重建：Traing_Progress/organized_20260309/visual_compare/best_vs_latest_20260309/recon_best_baseline_step8_curve_stdguard_v2
- 最新穩定權重重建：Traing_Progress/organized_20260309/visual_compare/best_vs_latest_20260309/recon_latest_stable_step0p08_mcf
- 對照圖：Traing_Progress/organized_20260309/visual_compare/best_vs_latest_20260309/compare_panels