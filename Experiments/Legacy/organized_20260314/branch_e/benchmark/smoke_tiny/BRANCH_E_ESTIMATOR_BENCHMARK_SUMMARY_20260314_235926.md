# Branch E Estimator Benchmark Summary

- generated_at: 2026-03-14 23:59:26
- weights_path: `Experiments/Legacy/organized_20260313/round18/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756/weights/best_tradeoff.pth.tar`
- chosen_probe_candidates: `be_ctrl_edge, be_edge_band, be_soft_band, be_soft`
- best_non_control_estimator: `edge_band_refine`
- improvement_vs_edge_abs_px: 38.6844
- selection_policy: 0.8px clean+convolved avg abs_center_err primary, delta_center secondary, step_err tertiary, sign_acc tie-breaker

| scale | domain | estimator | abs_center_err_px | delta_center_err_px | step_err_rel | sign_acc | bias_x | bias_y | trainable |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0.8px | clean | algebraic_fit_raw | 185.0115 | 0.7503 | 0.9367 | 1.0000 | -129.9280 | -131.7094 | 0 |
| 0.8px | clean | edge_algebraic_fit | 200.5269 | 0.9173 | 1.1415 | 0.0000 | -140.6730 | -142.9025 | 1 |
| 0.8px | clean | edge_band_refine | 36.5949 | 1.0344 | 1.2435 | 0.5000 | -25.1045 | -26.6159 | 1 |
| 0.8px | clean | edge_centroid | 93.0720 | 0.9072 | 1.1122 | 0.5000 | -65.0196 | -66.5904 | 1 |
| 0.8px | clean | soft_band_refine | 160.2999 | 0.8389 | 1.0414 | 0.2500 | -112.5157 | -114.1741 | 1 |
| 0.8px | clean | soft_centroid | 168.1606 | 0.8102 | 1.0106 | 0.5000 | -118.0469 | -119.7596 | 1 |
| 0.8px | convolved | algebraic_fit_raw | 184.9491 | 0.7516 | 0.9383 | 1.0000 | -129.8796 | -131.6695 | 0 |
| 0.8px | convolved | edge_algebraic_fit | 187.4641 | 1.2474 | 1.2782 | 0.2500 | -131.6100 | -133.4953 | 1 |
| 0.8px | convolved | edge_band_refine | 129.8736 | 10.8378 | 8.9619 | 0.7500 | -91.0441 | -92.6150 | 1 |
| 0.8px | convolved | edge_centroid | 150.7654 | 6.5361 | 5.2779 | 0.7500 | -105.7664 | -107.4391 | 1 |
| 0.8px | convolved | soft_band_refine | 169.7774 | 1.4009 | 0.9984 | 0.7500 | -119.1921 | -120.9007 | 1 |
| 0.8px | convolved | soft_centroid | 174.8956 | 1.1056 | 0.8433 | 0.7500 | -122.7943 | -124.5368 | 1 |

## 0.8px Clean/Convolved Ranking

| estimator | trainable | probe_candidate | avg_abs | avg_delta | avg_step | avg_sign | sr_gap |
|---|---:|---|---:|---:|---:|---:|---:|
| edge_band_refine | 1 | be_edge_band | 83.2343 | 5.9361 | 5.1027 | 0.6250 | nan |
| edge_centroid | 1 | be_ctrl_edge | 121.9187 | 3.7216 | 3.1951 | 0.6250 | nan |
| soft_band_refine | 1 | be_soft_band | 165.0386 | 1.1199 | 1.0199 | 0.5000 | nan |
| soft_centroid | 1 | be_soft | 171.5281 | 0.9579 | 0.9269 | 0.6250 | nan |
| algebraic_fit_raw | 0 | - | 184.9803 | 0.7510 | 0.9375 | 1.0000 | nan |
| edge_algebraic_fit | 1 | be_edge_algfit | 193.9955 | 1.0823 | 1.2098 | 0.1250 | nan |
