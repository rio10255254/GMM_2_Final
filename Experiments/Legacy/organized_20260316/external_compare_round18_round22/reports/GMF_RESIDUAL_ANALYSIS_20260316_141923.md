# GMF Residual Analysis — 20260316_141923

## Summary

- Pitches analyzed: 3
- pitch1um_y_100: 100 aligned frames, sg drift=0.094126, h drift=0.118317
- pitch0p1um_y_60: 60 aligned frames, sg drift=-0.063645, h drift=-0.032134
- pitch0p01um_y_40: 40 aligned frames, sg drift=-0.054832, h drift=0.147947

## Per-Pitch Results

### pitch1um_y_100

| Metric | R22_stepguard | R22_hold |
|--------|--------------|----------|
| N frames | 100 | 100 |
| Mean residual (px) | 0.068950 | 3.568970 |
| Std residual (px) | 0.223464 | 0.223689 |
| Max \|residual\| (px) | 0.575000 | 4.180000 |
| Drift (Pearson r) | 0.094126 | 0.118317 |
| Std(steps) | 0.245431 | 0.288654 |
| Lag-1 autocorr | 0.099548 | 0.026597 |

### pitch0p1um_y_60

| Metric | R22_stepguard | R22_hold |
|--------|--------------|----------|
| N frames | 60 | 60 |
| Mean residual (px) | 0.989033 | 2.579050 |
| Std residual (px) | 0.212982 | 0.254851 |
| Max \|residual\| (px) | 1.511000 | 3.305000 |
| Drift (Pearson r) | -0.063645 | -0.032134 |
| Std(steps) | 0.333639 | 0.285453 |
| Lag-1 autocorr | -0.035291 | 0.198915 |

Outlier frames (only for pitch0p1um_y_60, max 10):

| FileName | R18 step | R22sg step | diff |
|----------|----------|------------|------|
| VisionTop_20251029185446254.bmp | -0.552000 | -1.245000 | -0.693000 |
| VisionTop_20251029190030535.bmp | -0.493000 | -1.149000 | -0.656000 |
| VisionTop_20251029190156571.bmp | -0.789000 | -1.725000 | -0.936000 |

### pitch0p01um_y_40

| Metric | R22_stepguard | R22_hold |
|--------|--------------|----------|
| N frames | 40 | 40 |
| Mean residual (px) | 0.066600 | 0.937550 |
| Std residual (px) | 0.164230 | 0.221131 |
| Max \|residual\| (px) | 0.429000 | 1.497000 |
| Drift (Pearson r) | -0.054832 | 0.147947 |
| Std(steps) | 0.169440 | 0.189303 |
| Lag-1 autocorr | 0.234002 | 0.214462 |

## Core Questions

Q1: Is residual random or drift?  Residual looks more random than drifting: no pitch exceeds |Pearson r| > 0.3.

Q2: Are outlier frames clustered or uniformly distributed?  Outlier frames appear spread out in pitch0p1um_y_60 (max gap 32 >= n_frames/3).

Q3: Do R22h and R22sg show different residual patterns?  R22_hold and R22_stepguard show different residual patterns: pitch1um_y_100 exceeds the 0.1 threshold.
