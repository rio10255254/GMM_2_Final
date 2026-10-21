# R55 Results

## Purpose

R55 tests the source-style rebuilt training data after the Lab data audit found
unrealistic high-contrast targets in earlier packages.

## Current Plan

- Use the repaired 6000-pair R53-style package as the first formal training set.
- Keep the larger repaired pool out of the first run to avoid changing too many
  variables at once.
- Preserve the R53 stable training recipe: scratch training, batch 16, 4 workers,
  boundary geometry enabled, and PSF-forward loss disabled.

## Status

- Geometry preparation completed for the 6000-pair train package and the 1740-pair validation pool.
- Smoke training passed.
- Formal 50-epoch training completed.
- Real Lab checkboard reconstruction completed for best_tradeoff and latest.
- best_tradeoff passed the real checkboard corner gate against Lab R40.
- latest failed the real checkboard corner gate and should not be used.

## Result

| Case | Median corner shift | Tail shift | Corners > 5 px |
|---|---:|---:|---:|
| Lab R40 tradeoff control | 4.243 px | 5.000 px | 24.581% |
| R55 best_tradeoff | 2.828 px | 3.606 px | 21.788% |
| R55 latest | 8.485 px | 9.220 px | 51.397% |

R55 best_tradeoff is the current Lab-only candidate for external GMF follow-up.
It is not promoted without external GMF. The latest checkpoint confirms the
training can overrun into oversmoothing even while internal PSNR/SSIM improves.
