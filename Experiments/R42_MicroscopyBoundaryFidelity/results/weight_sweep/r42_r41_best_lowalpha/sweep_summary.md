# R42 低比例權重平均 sweep - COMBO ↔ r42_r41_best_lowalpha

COMBO checkpoint:`Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar`
候選 checkpoint:`Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r42_boundary_from_r41_20260505_145229/weights/best_tradeoff.pth.tar`

## Trade-off 表

| alpha | boundary PSNR | HF retention | boundary dist px | F1@1px | ring 8px | ring 0.8px | ring 0.08px |
|------:|--------------:|-------------:|-----------------:|-------:|---------:|-----------:|------------:|
| 0.01 | 20.6423 | 0.2048 | 7.6609 | 0.6310 | 0.1387 | 0.1567 | 0.1121 |
| 0.02 | 20.7337 | 0.2087 | 7.5530 | 0.6368 | 0.1458 | 0.1538 | 0.1140 |
| 0.03 | 20.8252 | 0.2127 | 7.5293 | 0.6420 | 0.1399 | 0.1487 | 0.1232 |
| 0.05 | 21.0094 | 0.2214 | 7.5402 | 0.6518 | 0.1483 | 0.1555 | 0.1291 |

## Verdict

- guarded trade-off found:**False**
- 理由:no alpha satisfies both boundary-capacity and local ring-guard thresholds
- 最佳 boundary-only alpha:**0.05**
