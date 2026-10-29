# ROUND17_STEPFIX Checkpoint Audit Summary

- best_candidate: r17_ec_stepmag
- selected_checkpoint: Traing_Progress/training_progress_GESR_v1_v5_ST8_SWP_r17es_20260313_130154/weights/best_tradeoff.pth.tar
- selection_policy: center-lock checkpoint audit across 0.08/0.8/8.0 after 0.8px center-stability pre-rank

| candidate | family | deploy | checkpoint |
| --- | ---: | ---: | --- |
| r17_ec_stepmag | 350.388 | -119.067 | checkpoint_8px |
| r17_af_stepmag | 358.291 | -129.163 | checkpoint_0p08 |
| r17_ec_balanced | 350.216 | -130.425 | checkpoint_0p08 |
| r17_ec_gradboost | 350.177 | -130.425 | checkpoint_0p08 |