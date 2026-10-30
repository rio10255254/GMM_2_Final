# BRANCH_E_ESTIMATOR_PROBE Summary

- best_family_candidate: be_soft_band
- selection_policy: 0.8px estimator probe rank: center_err primary, step_err secondary, sign tertiary, baseline-best lightly penalized

| candidate | method | base-best | c0 | cbest | dc | sbest | ds | ann | seq | bench_abs | family |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| be_soft_band | soft_band_refine | 1 | 0.1862 | 0.1862 | 0.0000 | 0.5804 | 0.0000 | 1.0000 | 0.6999 | 130.3228 | -15.043 |
| be_ctrl_edge | edge_centroid | 0 | 6.9723 | 7.8281 | 0.8558 | 0.9419 | -0.4136 | 0.7000 | 0.7028 | 103.1054 | -891.923 |
| be_edge_band | edge_band_refine | 0 | 9.0090 | 9.6406 | 0.6316 | 1.0209 | -0.1810 | 0.6667 | 0.6997 | 82.7432 | -1098.101 |
| be_soft | soft_centroid | 0 | nan | nan | nan | nan | nan | nan | 0.7071 | 133.1772 | -1493.497 |