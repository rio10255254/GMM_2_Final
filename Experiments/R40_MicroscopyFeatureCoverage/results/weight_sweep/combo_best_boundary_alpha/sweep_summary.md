# R40 權重平均 sweep — COMBO ↔ r40_combo_best

COMBO checkpoint:`Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar`
候選 checkpoint:`Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260504_145920/weights/best_tradeoff.pth.tar`

## Trade-off 表

| alpha | micro PSNR | HF retention | edge retention | ring 8px | ring 0.8px | ring 0.08px |
|------:|-----------:|-------------:|---------------:|---------:|-----------:|------------:|
| 0.47 | 27.0612 | 0.3587 | 0.7536 | 0.1616 | 0.1314 | 0.1324 |

## Verdict

- guarded trade-off found:**False**
- 理由:no alpha satisfies both microscopy-capacity and ring-guard thresholds
- 最佳 capacity-only alpha:**0.47**
