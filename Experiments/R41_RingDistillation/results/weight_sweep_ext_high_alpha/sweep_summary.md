# R41 權重平均 sweep — COMBO ↔ r41_kd_from_a045

COMBO checkpoint:`Experiments/Training_Runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar`
候選 checkpoint:`Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r41_kd_from_a045_20260505_103028/weights/best_tradeoff.pth.tar`

## Trade-off 表

| alpha | micro PSNR | HF retention | edge retention | ring 8px | ring 0.8px | ring 0.08px |
|------:|-----------:|-------------:|---------------:|---------:|-----------:|------------:|
| 0.45 | 26.1840 | 0.3012 | 0.7210 | 0.1577 | 0.1515 | 0.1322 |
| 0.50 | 26.6662 | 0.3358 | 0.7358 | 0.1534 | 0.1595 | 0.1475 |

## Verdict

- guarded trade-off found:**False**
- 理由:no alpha satisfies both microscopy-capacity and ring-guard thresholds
- 最佳 capacity-only alpha:**0.50**
