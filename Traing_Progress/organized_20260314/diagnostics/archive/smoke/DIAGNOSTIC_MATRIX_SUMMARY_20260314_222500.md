# Diagnostic Matrix Summary
- generated_at: 2026-03-14 22:25:00
- weights_path: `D:\GMM_2_Final\Traing_Progress\organized_20260313\round18\selected\runs\training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756\weights\best_tradeoff.pth.tar`
- truth_source: generator_replay
- recommended_branch: **Branch L**
- rationale: Estimator gap on clean/convolved is small; remaining error is more likely target/label alignment on SR.

| scale | domain | estimator | abs_center_err_px | delta_center_err_px | step_err_rel | sign_acc | bias_x | bias_y | frames | pairs |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.8px | clean | algebraic_fit | 185.0115 | 0.7503 | 0.9367 | 1.0000 | -129.9280 | -131.7094 | 5 | 4 |
| 0.8px | clean | edge_centroid | 93.0720 | 0.9072 | 1.1122 | 0.5000 | -65.0197 | -66.5905 | 5 | 4 |
| 0.8px | convolved | algebraic_fit | 184.9491 | 0.7516 | 0.9383 | 1.0000 | -129.8796 | -131.6695 | 5 | 4 |
| 0.8px | convolved | edge_centroid | 150.7654 | 6.5361 | 5.2779 | 0.7500 | -105.7664 | -107.4391 | 5 | 4 |
| 0.8px | sr_round18 | algebraic_fit | 184.4881 | 0.7532 | 0.9403 | 1.0000 | -129.5362 | -131.3605 | 5 | 4 |
| 0.8px | sr_round18 | edge_centroid | 96.0716 | 1.3965 | 1.1332 | 0.7500 | -67.2206 | -68.6355 | 5 | 4 |

## Decision Signals
- af_gain_clean: -91.9395
- af_gain_convolved: -34.1837
- best_sr_minus_best_convolved: -54.6938
- estimator_bias_present: False
- sr_mismatch_present: False
