# R40 權重平均 sweep — COMBO ↔ r40_micro_capacity_combo

COMBO checkpoint:`Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar`
候選 checkpoint:`Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260504_145920/weights/best_tradeoff.pth.tar`

## Trade-off 表

| alpha | micro PSNR | HF retention | edge retention | ring 8px | ring 0.8px | ring 0.08px |
|------:|-----------:|-------------:|---------------:|---------:|-----------:|------------:|
| 0.42 | 26.6228 | 0.3172 | 0.7343 | 0.1524 | 0.1448 | 0.1337 |
| 0.43 | 26.7150 | 0.3250 | 0.7386 | 0.1495 | 0.1448 | 0.1255 |
| 0.44 | 26.8039 | 0.3332 | 0.7417 | 0.1630 | 0.1411 | 0.1240 |

## Verdict

- guarded trade-off found:**True**
- 理由:guarded trade-off found at alpha=0.43
- 最佳 guarded alpha:**0.43**
