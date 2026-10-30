# R39 權重平均 sweep — COMBO ↔ r39_shape_mix_strong

COMBO checkpoint:`Experiments/Training_Runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar`
候選 checkpoint:`Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_strong_20260428_180728/weights/best_tradeoff.pth.tar`
門檻:shape PSNR ≥ 24.84、8px ≤ 0.155、0.8px ≤ 0.155、0.08px ≤ 0.135

## Trade-off 表

| alpha | shape PSNR | shape SSIM | ring 8px | ring 0.8px | ring 0.08px |
|------:|-----------:|-----------:|---------:|-----------:|------------:|
| 0.00 | 22.8411 | 0.8502 | 0.1389 | 0.1509 | 0.1185 |
| 0.10 | 23.5329 | 0.8604 | 0.1409 | 0.1540 | 0.1184 |
| 0.20 | 24.2538 | 0.8702 | 0.1380 | 0.1640 | 0.1157 |
| 0.30 | 25.0326 | 0.8798 | 0.1384 | 0.1507 | 0.1114 |
| 0.40 | 25.8894 | 0.8893 | 0.1379 | 0.1605 | 0.1082 |
| 0.50 | 26.8262 | 0.8987 | 0.1552 | 0.1487 | 0.1220 |
| 0.60 | 27.8053 | 0.9078 | 0.1629 | 0.1552 | 0.1203 |
| 0.70 | 28.7456 | 0.9160 | 0.1679 | 0.1567 | 0.1233 |
| 0.80 | 29.5349 | 0.9230 | 0.1858 | 0.1491 | 0.1431 |
| 0.90 | 30.0227 | 0.9286 | 0.1875 | 0.1629 | 0.1601 |
| 1.00 | 30.0722 | 0.9326 | 0.2004 | 0.1691 | 0.1750 |

## Verdict

- found:**True**
- 理由:sweet spot found at alpha=0.30
- 最佳 alpha:**0.30**(shape PSNR 25.0326、ring 8px 0.1384)
