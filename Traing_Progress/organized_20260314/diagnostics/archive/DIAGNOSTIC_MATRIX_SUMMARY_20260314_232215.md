# Diagnostic Matrix Summary
- generated_at: 2026-03-14 23:22:15
- weights_path: `Traing_Progress/organized_20260313/round18/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756/weights/best_tradeoff.pth.tar`
- truth_source: generator_replay
- recommended_branch: **Branch L**
- rationale: Estimator gap on clean/convolved is small; remaining error is more likely target/label alignment on SR.

| scale | domain | estimator | abs_center_err_px | delta_center_err_px | step_err_rel | sign_acc | bias_x | bias_y | frames | pairs |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.08px | clean | algebraic_fit | 137.0872 | 0.0798 | 0.9971 | 0.5750 | -23.7242 | -20.1247 | 150 | 120 |
| 0.08px | clean | edge_centroid | 82.9142 | 0.1131 | 1.3919 | 0.3083 | -14.1631 | -12.8459 | 150 | 120 |
| 0.08px | convolved | algebraic_fit | 137.0737 | 0.0798 | 0.9958 | 0.5417 | -23.7218 | -20.1233 | 150 | 120 |
| 0.08px | convolved | edge_centroid | 121.3703 | 2.9982 | 23.8962 | 0.4750 | -20.8939 | -17.5567 | 150 | 120 |
| 0.08px | sr_round18 | algebraic_fit | 137.0086 | 0.0796 | 0.9936 | 0.5500 | -23.6603 | -19.9709 | 150 | 120 |
| 0.08px | sr_round18 | edge_centroid | 84.1453 | 1.0747 | 9.0864 | 0.5250 | -12.3279 | -14.2726 | 150 | 120 |
| 0.8px | clean | algebraic_fit | 138.7895 | 0.7980 | 0.9974 | 0.5606 | -10.9635 | 8.0327 | 318 | 264 |
| 0.8px | clean | edge_centroid | 83.5683 | 1.1424 | 1.4054 | 0.4129 | -4.5532 | 6.4500 | 318 | 264 |
| 0.8px | convolved | algebraic_fit | 138.7729 | 0.7976 | 0.9969 | 0.5492 | -10.9579 | 8.0313 | 318 | 264 |
| 0.8px | convolved | edge_centroid | 122.6426 | 3.0021 | 2.3057 | 0.5417 | -8.4079 | 7.9394 | 318 | 264 |
| 0.8px | sr_round18 | algebraic_fit | 138.7702 | 0.7971 | 0.9963 | 0.5606 | -10.9663 | 7.9980 | 318 | 264 |
| 0.8px | sr_round18 | edge_centroid | 85.8518 | 1.1697 | 0.9585 | 0.7121 | -3.1456 | 7.2488 | 318 | 264 |
| 8px | clean | algebraic_fit | 113.7432 | 8.0105 | 1.0012 | 0.4917 | -3.1781 | 12.0164 | 150 | 120 |
| 8px | clean | edge_centroid | 65.6275 | 5.3953 | 0.6714 | 0.9083 | -2.9318 | 7.8725 | 150 | 120 |
| 8px | convolved | algebraic_fit | 113.7300 | 8.0099 | 1.0012 | 0.4917 | -3.1785 | 12.0177 | 150 | 120 |
| 8px | convolved | edge_centroid | 98.4519 | 7.9061 | 0.9259 | 0.6333 | -2.7744 | 10.7865 | 150 | 120 |
| 8px | sr_round18 | algebraic_fit | 113.6703 | 8.0004 | 1.0000 | 0.4250 | -3.0540 | 12.1253 | 150 | 120 |
| 8px | sr_round18 | edge_centroid | 67.5150 | 4.9247 | 0.6032 | 0.9833 | -2.7904 | 9.2091 | 150 | 120 |

## Decision Signals
- af_gain_clean: -55.2212
- af_gain_convolved: -16.1304
- best_sr_minus_best_convolved: -36.7908
- estimator_bias_present: False
- sr_mismatch_present: False
