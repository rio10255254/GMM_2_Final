# 20260603 calibrated GMF readout

This is an exploratory same-sample readout for the new 20260603 capture system.
It is not directly comparable to the official three-pitch project GMF results.

## Calibration

- PI commanded movement: 1.0 um
- Camera pixel size: 3.45 um x 3.45 um
- Objective magnification: 20x
- Effective object-plane pixel size: 0.1725 um/px
- Expected image displacement: 5.797101 px per 1.0 um PI move

## Main readout

The external tool wrote 10 frames for each case. The earliest image,
`Image__2026-06-03__20-22-34.bmp`, is not present in any `GMF_score.txt`.

| Case | Frames | Mean step (px) | Median step (px) | Step std (px) | Step std (um) | Mean step error vs 1 um |
|---|---:|---:|---:|---:|---:|---:|
| raw input | 10 | 5.712333 | 5.777000 | 0.263221 | 0.045406 | -1.46% |
| R39R40 default | 10 | 5.709889 | 5.788000 | 0.269302 | 0.046455 | -1.50% |
| R39R40 reg300 | 10 | 5.709889 | 5.782000 | 0.271962 | 0.046913 | -1.50% |
| COMBO reference | 10 | 5.709889 | 5.782000 | 0.271962 | 0.046913 | -1.50% |
| PSF bypass extreme | 10 | 5.708889 | 5.780000 | 0.272257 | 0.046964 | -1.52% |

No z > 5 GMF failures were found.

## Warm-up-step diagnostic

All cases have a small first step near 5.0 px. If that first interval is treated
as a sequence warm-up diagnostic rather than removed from the headline value,
the remaining mean step is almost exactly the expected 5.797101 px.

| Case | Mean step after first (px) | Step std after first (px) | Error vs expected |
|---|---:|---:|---:|
| raw input | 5.800375 | 0.090467 | +0.06% |
| R39R40 default | 5.800500 | 0.087724 | +0.06% |
| R39R40 reg300 | 5.801125 | 0.091062 | +0.07% |
| COMBO reference | 5.801125 | 0.091062 | +0.07% |
| PSF bypass extreme | 5.800250 | 0.090928 | +0.05% |

## Interpretation

- The GMF scale is consistent with the provided 1.0 um PI move and the optical
  calibration.
- With all steps included, the raw input has the lowest step variation.
- Among reconstructed outputs, R39R40 default is the lowest-variation case.
- The visually preferred reg300 case does not improve GMF stability here; it is
  essentially tied with COMBO on this score file.
- PSF bypass is not supported by this GMF readout; it is slightly worse than the
  default R39R40 case.
- Because this is only a 10-frame same-sample readout, use it as directional
  evidence only.
