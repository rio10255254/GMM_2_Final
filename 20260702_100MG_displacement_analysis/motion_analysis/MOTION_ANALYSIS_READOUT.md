# 20260702 100MG displacement reconstruction analysis

Primary result uses the bottom-left dot array and binarized dark-pattern phase correlation.
Full-frame edge matching is included as a stress test of how easy the whole image is to register.

## Primary displacement result

| dataset | image | steps | median |dx| px | std |dx| px | median dx px | response | inferred um/px from command |
|---|---|---:|---:|---:|---:|---:|---:|
| x_1um | Raw | 49 | 14.6090 | 0.1442 | -14.6090 | 0.9094 | 0.06845 |
| x_1um | R61 v16 PSF-off | 49 | 14.5779 | 0.1314 | -14.5779 | 0.9184 | 0.06860 |
| x_0p5um | Raw | 50 | 7.2556 | 0.7635 | -7.2556 | 0.9456 | 0.06891 |
| x_0p5um | R61 v16 PSF-off | 50 | 7.2669 | 0.7582 | -7.2669 | 0.9554 | 0.06881 |

## Primary displacement after excluding intervals with time gap > 30 s

| dataset | image | steps | median |dx| px | std |dx| px | median dx px | response | inferred um/px from command |
|---|---|---:|---:|---:|---:|---:|---:|
| x_1um | Raw | 47 | 14.6084 | 0.1274 | -14.6084 | 0.9073 | 0.06845 |
| x_1um | R61 v16 PSF-off | 47 | 14.5731 | 0.1105 | -14.5731 | 0.9159 | 0.06862 |
| x_0p5um | Raw | 47 | 7.2481 | 0.0895 | -7.2481 | 0.9461 | 0.06898 |
| x_0p5um | R61 v16 PSF-off | 47 | 7.2562 | 0.0882 | -7.2562 | 0.9561 | 0.06891 |

## Full-frame edge stress test

| dataset | image | move-like steps | median |dx| px | std dx px | response |
|---|---|---:|---:|---:|---:|
| x_1um | Raw | 9/49 | 0.0813 | 5.6595 | 0.3383 |
| x_1um | R61 v16 PSF-off | 49/49 | 14.6911 | 0.1730 | 0.6206 |
| x_0p5um | Raw | 8/50 | 0.1105 | 2.9777 | 0.2613 |
| x_0p5um | R61 v16 PSF-off | 50/50 | 7.2232 | 0.7727 | 0.6958 |

## Interpretation notes

- Primary ROI-based measurement says Raw and R61 v16 preserve nearly the same commanded displacement.
- The x_0.5um full-span standard deviation is inflated by long-pause intervals; the gap-filtered table is the cleaner stability view.
- R61 v16 makes full-frame edge registration much more stable, especially when raw intensity/blur causes local matching to collapse.
- These are local image-registration results, not external GMF scores.
