# Branch E Estimator Benchmark Summary

- generated_at: 2026-03-15 15:17:02
- weights_path: `Experiments/Legacy/organized_20260313/round18/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756/weights/best_tradeoff.pth.tar`
- chosen_probe_candidates: `be_ctrl_edge, be_edge_band, be_soft_band, be_soft`
- best_non_control_estimator: `edge_band_refine`
- improvement_vs_edge_abs_px: 20.3622
- selection_policy: 0.8px clean+convolved avg abs_center_err primary, delta_center secondary, step_err tertiary, sign_acc tie-breaker

| scale | domain | estimator | abs_center_err_px | delta_center_err_px | step_err_rel | sign_acc | bias_x | bias_y | trainable |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0.08px | clean | algebraic_fit_raw | 137.0872 | 0.0798 | 0.9971 | 0.5750 | -23.7242 | -20.1247 | 0 |
| 0.08px | clean | edge_algebraic_fit | 155.3096 | 0.1135 | 1.4031 | 0.1167 | -25.8645 | -23.6842 | 1 |
| 0.08px | clean | edge_band_refine | 51.9587 | 0.1303 | 1.5757 | 0.3667 | -8.7677 | -8.9268 | 1 |
| 0.08px | clean | edge_centroid | 82.9142 | 0.1131 | 1.3919 | 0.3083 | -14.1631 | -12.8459 | 1 |
| 0.08px | clean | soft_band_refine | 127.0489 | 0.0821 | 1.0263 | 0.4917 | -22.3623 | -19.3014 | 1 |
| 0.08px | clean | soft_centroid | 130.2989 | 0.0842 | 1.0522 | 0.3333 | -22.8224 | -19.5163 | 1 |
| 0.08px | convolved | algebraic_fit_raw | 137.0737 | 0.0798 | 0.9958 | 0.5417 | -23.7218 | -20.1233 | 0 |
| 0.08px | convolved | edge_algebraic_fit | 140.3607 | 1.0061 | 8.1240 | 0.4917 | -24.0134 | -20.9270 | 1 |
| 0.08px | convolved | edge_band_refine | 112.5083 | 4.8019 | 38.3918 | 0.4667 | -19.1510 | -16.4253 | 1 |
| 0.08px | convolved | edge_centroid | 121.3703 | 2.9982 | 23.8962 | 0.4750 | -20.8939 | -17.5567 | 1 |
| 0.08px | convolved | soft_band_refine | 131.8440 | 0.4602 | 3.4812 | 0.5167 | -23.1897 | -19.8423 | 1 |
| 0.08px | convolved | soft_centroid | 133.4856 | 0.3184 | 2.4481 | 0.5083 | -23.3909 | -19.8711 | 1 |
| 0.08px | sr_round18 | algebraic_fit_raw | 137.0086 | 0.0796 | 0.9936 | 0.5500 | -23.6603 | -19.9709 | 0 |
| 0.08px | sr_round18 | edge_algebraic_fit | 153.0569 | 0.6182 | 5.0780 | 0.4500 | -25.2794 | -23.1426 | 1 |
| 0.08px | sr_round18 | edge_band_refine | 53.4625 | 1.7170 | 14.2310 | 0.5333 | -5.8790 | -11.3724 | 1 |
| 0.08px | sr_round18 | edge_centroid | 84.1453 | 1.0747 | 9.0864 | 0.5250 | -12.3279 | -14.2726 | 1 |
| 0.08px | sr_round18 | soft_band_refine | 126.6096 | 0.1334 | 1.3199 | 0.5833 | -21.8703 | -18.9248 | 1 |
| 0.08px | sr_round18 | soft_centroid | 129.9930 | 0.1068 | 1.1251 | 0.5750 | -22.3995 | -19.1797 | 1 |
| 0.8px | clean | algebraic_fit_raw | 138.7895 | 0.7980 | 0.9974 | 0.5606 | -10.9635 | 8.0327 | 0 |
| 0.8px | clean | edge_algebraic_fit | 158.2233 | 1.1073 | 1.3723 | 0.0606 | -13.3417 | 8.7341 | 1 |
| 0.8px | clean | edge_band_refine | 52.1539 | 1.3179 | 1.5945 | 0.4280 | -0.5078 | 6.4542 | 1 |
| 0.8px | clean | edge_centroid | 83.5683 | 1.1424 | 1.4054 | 0.4129 | -4.5532 | 6.4500 | 1 |
| 0.8px | clean | soft_band_refine | 127.7161 | 0.7860 | 0.9822 | 0.6667 | -8.8463 | 8.3395 | 1 |
| 0.8px | clean | soft_centroid | 131.4871 | 0.8063 | 1.0076 | 0.5795 | -9.5735 | 8.2212 | 1 |
| 0.8px | convolved | algebraic_fit_raw | 138.7729 | 0.7976 | 0.9969 | 0.5492 | -10.9579 | 8.0313 | 0 |
| 0.8px | convolved | edge_algebraic_fit | 142.7013 | 1.3405 | 1.1863 | 0.4697 | -11.6172 | 8.0378 | 1 |
| 0.8px | convolved | edge_band_refine | 113.3324 | 4.6744 | 3.5295 | 0.5455 | -6.9650 | 7.9503 | 1 |
| 0.8px | convolved | edge_centroid | 122.6426 | 3.0021 | 2.3057 | 0.5417 | -8.4079 | 7.9394 | 1 |
| 0.8px | convolved | soft_band_refine | 132.9295 | 0.9164 | 0.9651 | 0.5795 | -9.5625 | 8.2745 | 1 |
| 0.8px | convolved | soft_centroid | 134.8672 | 0.8441 | 0.9632 | 0.5795 | -10.0538 | 8.1710 | 1 |
| 0.8px | sr_round18 | algebraic_fit_raw | 138.7702 | 0.7971 | 0.9963 | 0.5606 | -10.9663 | 7.9980 | 0 |
| 0.8px | sr_round18 | edge_algebraic_fit | 156.0585 | 1.0794 | 1.1197 | 0.3864 | -12.7055 | 8.5394 | 1 |
| 0.8px | sr_round18 | edge_band_refine | 54.8245 | 1.6486 | 1.2261 | 0.6932 | 1.5419 | 7.6079 | 1 |
| 0.8px | sr_round18 | edge_centroid | 85.8518 | 1.1697 | 0.9585 | 0.7121 | -3.1456 | 7.2488 | 1 |
| 0.8px | sr_round18 | soft_band_refine | 127.7022 | 0.7420 | 0.9182 | 0.8220 | -8.6281 | 8.6825 | 1 |
| 0.8px | sr_round18 | soft_centroid | 131.5058 | 0.7588 | 0.9444 | 0.8144 | -9.3435 | 8.4978 | 1 |
| 8px | clean | algebraic_fit_raw | 113.7432 | 8.0105 | 1.0012 | 0.4917 | -3.1781 | 12.0164 | 0 |
| 8px | clean | edge_algebraic_fit | 133.1015 | 9.3194 | 1.1604 | 0.2167 | -3.5828 | 13.5919 | 1 |
| 8px | clean | edge_band_refine | 37.4406 | 3.8817 | 0.4768 | 0.9250 | -2.5643 | 5.6802 | 1 |
| 8px | clean | edge_centroid | 65.6275 | 5.3953 | 0.6714 | 0.9083 | -2.9318 | 7.8725 | 1 |
| 8px | clean | soft_band_refine | 104.0543 | 7.3762 | 0.9220 | 0.9417 | -3.2438 | 11.8061 | 1 |
| 8px | clean | soft_centroid | 107.1432 | 7.6071 | 0.9509 | 0.9250 | -3.2035 | 11.8846 | 1 |
| 8px | convolved | algebraic_fit_raw | 113.7300 | 8.0099 | 1.0012 | 0.4917 | -3.1785 | 12.0177 | 0 |
| 8px | convolved | edge_algebraic_fit | 118.0619 | 8.1773 | 1.0101 | 0.4000 | -3.4866 | 12.3776 | 1 |
| 8px | convolved | edge_band_refine | 90.2796 | 8.6137 | 0.9378 | 0.6500 | -2.5675 | 10.0105 | 1 |
| 8px | convolved | edge_centroid | 98.4519 | 7.9061 | 0.9259 | 0.6333 | -2.7744 | 10.7865 | 1 |
| 8px | convolved | soft_band_refine | 108.5054 | 7.7151 | 0.9622 | 0.7167 | -3.2330 | 12.0771 | 1 |
| 8px | convolved | soft_centroid | 110.0424 | 7.8094 | 0.9752 | 0.6917 | -3.1935 | 12.0775 | 1 |
| 8px | sr_round18 | algebraic_fit_raw | 113.6703 | 8.0004 | 1.0000 | 0.4250 | -3.0540 | 12.1253 | 0 |
| 8px | sr_round18 | edge_algebraic_fit | 131.1040 | 8.8525 | 1.1002 | 0.2750 | -2.8736 | 13.4981 | 1 |
| 8px | sr_round18 | edge_band_refine | 40.0023 | 3.5517 | 0.3907 | 0.9917 | -2.4719 | 7.7208 | 1 |
| 8px | sr_round18 | edge_centroid | 67.5150 | 4.9247 | 0.6032 | 0.9833 | -2.7904 | 9.2091 | 1 |
| 8px | sr_round18 | soft_band_refine | 104.0037 | 7.3211 | 0.9150 | 0.9417 | -2.7920 | 12.1491 | 1 |
| 8px | sr_round18 | soft_centroid | 107.1663 | 7.5523 | 0.9440 | 0.9583 | -2.8175 | 12.1832 | 1 |

## 0.8px Clean/Convolved Ranking

| estimator | trainable | probe_candidate | avg_abs | avg_delta | avg_step | avg_sign | sr_gap |
|---|---:|---|---:|---:|---:|---:|---:|
| edge_band_refine | 1 | be_edge_band | 82.7432 | 2.9961 | 2.5620 | 0.4867 | -58.5079 |
| edge_centroid | 1 | be_ctrl_edge | 103.1054 | 2.0722 | 1.8556 | 0.4773 | -36.7908 |
| soft_band_refine | 1 | be_soft_band | 130.3228 | 0.8512 | 0.9736 | 0.6231 | -5.2273 |
| soft_centroid | 1 | be_soft | 133.1772 | 0.8252 | 0.9854 | 0.5795 | -3.3614 |
| algebraic_fit_raw | 0 | - | 138.7812 | 0.7978 | 0.9971 | 0.5549 | -0.0027 |
| edge_algebraic_fit | 1 | be_edge_algfit | 150.4623 | 1.2239 | 1.2793 | 0.2652 | 13.3572 |
