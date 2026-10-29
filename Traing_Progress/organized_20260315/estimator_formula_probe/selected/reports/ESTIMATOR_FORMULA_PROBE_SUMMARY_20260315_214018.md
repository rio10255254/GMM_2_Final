# Estimator Formula Probe Summary

- generated_at: 2026-03-15 21:40:18
- checkpoint: `Traing_Progress/organized_20260313/round18/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756/weights/best_tradeoff.pth.tar`
- macro_policy_estimator: `edge_band_refine`
- macro_guard_pass: `True`
- round21_ready: `False`
- blocked_reason: No mid-scale estimator variant passed the calibrated center+step gate.

| candidate | geom_method | center_err | step_err | seq_sign | center_improve | passes_mid_gate |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| soft_band | soft_band_refine | 0.1862 | 0.5804 | 0.7005 | 0.9733 | False |
| soft_band_sharp | soft_band_sharp | 0.1689 | 0.6700 | 0.7005 | 0.9758 | False |
| soft_band_stepmix | soft_band_stepmix | 0.3253 | 0.7121 | 0.7005 | 0.9533 | False |
| soft_band_light | soft_band_light | 0.3845 | 0.7841 | 0.7005 | 0.9449 | False |
| soft_band_stepmix_sharp | soft_band_stepmix_sharp | 0.3091 | 0.8417 | 0.7005 | 0.9557 | False |
| edge_ctrl | edge_centroid | 6.9723 | 1.3555 | 0.7005 | 0.0000 | False |
