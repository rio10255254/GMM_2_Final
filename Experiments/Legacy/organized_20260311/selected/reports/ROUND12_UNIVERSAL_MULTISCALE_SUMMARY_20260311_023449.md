# Round12 Universal Multiscale Summary

- best_candidate: universal_sign_guard
- selected_checkpoint: Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_usg_20260311_022337/weights/best_tradeoff.pth.tar
- selection_policy: prefer 0.8px checkpoint for winning candidate

| candidate | s0.08 | s0.8 | s8 | min_ann_sign | min_seq_sign | max_center | max_step | max_thick | universal |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| universal_sign_guard | 16.690 | 21.728 | 22.527 | 0.7500 | 0.5921 | 0.3988 | 0.5013 | 0.0177 | 38.449 |
| universal_clean_anchor | 11.358 | 11.358 | 11.358 | 0.7500 | 0.5882 | 0.4837 | 0.6065 | 0.0229 | 32.477 |
| universal_defect_anchor | 11.285 | 11.285 | 11.285 | 0.7500 | 0.5882 | 0.4837 | 0.6065 | 0.0229 | 32.259 |
| universal_balanced_bridge | 11.285 | 11.285 | 11.285 | 0.7500 | 0.5882 | 0.4837 | 0.6065 | 0.0229 | 32.259 |
| universal_macro_lock | 11.327 | 13.408 | 12.950 | 0.7500 | 0.5882 | 0.4837 | 0.6065 | 0.0229 | 27.762 |