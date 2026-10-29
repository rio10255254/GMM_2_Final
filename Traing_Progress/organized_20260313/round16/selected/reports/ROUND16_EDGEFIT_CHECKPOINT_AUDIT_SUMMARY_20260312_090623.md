# ROUND16_EDGEFIT Checkpoint Audit Summary

- best_candidate: r16_edge_highcenter
- selected_checkpoint: Traing_Progress/training_progress_GESR_v1_v5_ST8_SWP_r16eh_20260312_090336/weights/best_tradeoff.pth.tar
- selection_policy: center-lock checkpoint audit across 0.08/0.8/8.0 after 0.8px center-stability pre-rank

| candidate | family | deploy | checkpoint |
| --- | ---: | ---: | --- |
| r16_edge_highcenter | 219.783 | -219.339 | checkpoint_8px |
| r16_algfit_pure | 228.202 | -228.268 | checkpoint_0p08 |
| r16_algfit_driftfocus | 228.383 | -229.616 | checkpoint_0p08 |
| r16_algfit_lightmono | 222.699 | -229.754 | checkpoint_0p08 |