# BRANCH_E_ESTIMATOR_PROBE Audit Summary

- control_candidate: be_ctrl_edge
- best_candidate: be_soft_band
- selected_checkpoint: Traing_Progress/organized_20260314/branch_e/selected/runs/training_progress_GESR_v1_v5_ST0p8_SWP_besb_20260315_152453/weights/best_tradeoff.pth.tar
- center_improvement_vs_control: 7.641896
- estimator_probe_success: False

| candidate | method | base-best | c0 | cbest | dc | sbest | ds | ann | seq | score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| be_soft_band | soft_band_refine | 1 | 0.1862 | 0.1862 | 0.0000 | 0.5804 | 0.0000 | 1.0000 | 0.7005 | -64.872 |
| be_ctrl_edge | edge_centroid | 1 | 7.8281 | 7.8281 | 0.0000 | 0.9419 | 0.0000 | 0.7000 | 0.7041 | -939.771 |
| be_edge_band | edge_band_refine | 1 | 9.6406 | 9.6406 | 0.0000 | 1.0209 | 0.0000 | 0.6667 | 0.7006 | -1129.372 |
| be_soft | soft_centroid | 1 | nan | nan | nan | nan | nan | nan | 0.7077 | nan |
