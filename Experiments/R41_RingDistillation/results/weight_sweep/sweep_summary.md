# R41 權重平均 sweep — COMBO ↔ r41_kd_from_a045

COMBO checkpoint:`D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525\weights\best_tradeoff.pth.tar`
候選 checkpoint:`D:\GMM_2_Final\Traing_Progress\training_progress_GESR_v1_v5_ST0p8_SWP_r41_kd_from_a045_20260505_103028\weights\best_tradeoff.pth.tar`

## Trade-off 表

| alpha | micro PSNR | HF retention | edge retention | ring 8px | ring 0.8px | ring 0.08px |
|------:|-----------:|-------------:|---------------:|---------:|-----------:|------------:|
| 0.10 | 23.2282 | 0.2293 | 0.6787 | 0.1413 | 0.1464 | 0.1202 |
| 0.15 | 23.5350 | 0.2323 | 0.6852 | 0.1394 | 0.1562 | 0.1326 |
| 0.20 | 23.8927 | 0.2356 | 0.6903 | 0.1395 | 0.1598 | 0.1304 |
| 0.25 | 24.2972 | 0.2398 | 0.6938 | 0.1503 | 0.1473 | 0.1410 |
| 0.30 | 24.7405 | 0.2457 | 0.6978 | 0.1454 | 0.1409 | 0.1378 |
| 0.35 | 25.2092 | 0.2562 | 0.7027 | 0.1477 | 0.1517 | 0.1294 |
| 0.40 | 25.6941 | 0.2743 | 0.7095 | 0.1560 | 0.1481 | 0.1389 |

## Verdict

- guarded trade-off found:**False**
- 理由:no alpha satisfies both microscopy-capacity and ring-guard thresholds
- 最佳 capacity-only alpha:**0.40**
