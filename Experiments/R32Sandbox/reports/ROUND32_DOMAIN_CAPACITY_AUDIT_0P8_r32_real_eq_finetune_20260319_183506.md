# Process Probe Audit

- candidate: r32_real_eq_finetune
- checkpoint_path: Experiments/R32Sandbox/artifacts/training_progress_GESR_v1_v5_ST0p8_SWP_r32realeq_20260319_165431/weights/best_tradeoff.pth.tar
- geom_method: pairmix_algblend
- expect_dy: 0.80
- process_score: 2.682326
- passes_target: True

| metric | value |
| --- | ---: |
| best_epoch | 0 |
| best_epoch_is_baseline | True |
| epoch0_tradeoff_score | -0.006367 |
| epoch0_ann_seq_center_err_px | 0.201587 |
| epoch0_ann_seq_step_err_rel | 0.109591 |
| best_ann_seq_center_err_px | 0.201587 |
| best_ann_seq_step_err_rel | 0.109591 |
| best_minus_epoch0_center_err | 0.000000 |
| best_minus_epoch0_step_err | 0.000000 |
| best_ann_seq_sign_acc | 1.000000 |
| best_seq_val_sign_acc | 0.705049 |