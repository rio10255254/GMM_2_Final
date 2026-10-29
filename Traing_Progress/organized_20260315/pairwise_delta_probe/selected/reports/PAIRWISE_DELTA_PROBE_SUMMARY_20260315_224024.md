# Pairwise Delta Probe Summary

- generated_at: 2026-03-15 22:40:24
- checkpoint: `Traing_Progress/organized_20260313/round18/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756/weights/best_tradeoff.pth.tar`
- macro_policy_estimator: `edge_band_refine`
- macro_guard_pass: `True`
- round22_ready: `True`
- blocked_reason: none

| candidate | geom_method | center_err | step_err | seq_sign | center_improve | mid_pass | macro_pass | final_pass |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| pairmix_algblend | pairmix_algblend | 0.1845 | 0.0657 | 0.7005 | 0.9735 | True | True | True |
| pairmix_softcentroid | pairmix_softcentroid | 0.1851 | 0.4147 | 0.7005 | 0.9735 | True | True | True |
| pairmix_softblend | pairmix_softblend | 0.1854 | 0.4756 | 0.7005 | 0.9734 | False | True | False |
| soft_band | soft_band_refine | 0.1862 | 0.5804 | 0.7005 | 0.9733 | False | True | False |
| edge_ctrl | edge_centroid | 6.9723 | 1.3555 | 0.7005 | 0.0000 | False | True | False |
