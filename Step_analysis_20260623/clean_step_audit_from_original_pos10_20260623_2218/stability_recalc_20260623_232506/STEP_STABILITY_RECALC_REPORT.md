# Step Stability Recalculation Report

Generated: 2026-06-23T23:29:15

Calibration used: 2.5 um camera pixel / 20x objective = 0.125 um per image pixel.
Selected Step spacing: every 10 original positions, treated as 1.0 um = 8.0 px.

## Main Result: Sobel Edge Full 2048

| case | step median dx px | step std dx px | step std um | 95% CI std px | p95 abs error um | median response | confidence | improvement vs raw |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| Raw center crop | 8.0062 | 0.5123 | 0.06404 | 0.4455-0.6122 | 0.11161 | 0.3512 | medium | 1.00 |
| R39 reconstruction | 8.0248 | 0.0903 | 0.01129 | 0.0785-0.1079 | 0.02254 | 0.9571 | high | 5.67 |
| v14 reconstruction | 8.0246 | 0.0896 | 0.01120 | 0.0779-0.1071 | 0.02257 | 0.9583 | high | 5.72 |
| v16 reconstruction | 8.0241 | 0.0900 | 0.01125 | 0.0782-0.1075 | 0.02252 | 0.9575 | high | 5.69 |

## Same-Position Repeat Check

| case | repeat median mag px | repeat p95 mag px | repeat median mag um | median response | confidence |
|---|---:|---:|---:|---:|---|
| Raw center crop | 0.0314 | 0.0583 | 0.00392 | 0.3638 | medium |
| R39 reconstruction | 0.1205 | 0.2550 | 0.01506 | 0.9593 | high |
| v14 reconstruction | 0.1198 | 0.2515 | 0.01497 | 0.9602 | high |
| v16 reconstruction | 0.1209 | 0.2536 | 0.01511 | 0.9601 | high |

## Method Cross-Check: Step Scale

| case | method | median dx px | std dx px | median response | confidence |
|---|---|---:|---:|---:|---|
| Raw center crop | brightness, full 2048 | 0.7425 | 0.0614 | 0.0883 | low |
| Raw center crop | high-pass brightness, full 2048 | 0.7429 | 0.0614 | 0.0883 | low |
| Raw center crop | Sobel edge raw magnitude, full 2048 | 8.0062 | 0.5123 | 0.3512 | medium |
| Raw center crop | Sobel edge normalized, full 2048 | 8.0062 | 0.5123 | 0.3512 | medium |
| Raw center crop | Sobel edge raw magnitude, center 1536 | 8.0069 | 0.6056 | 0.3551 | medium |
| Raw center crop | Sobel edge raw magnitude, center 1024 | 8.0022 | 0.7417 | 0.3232 | low |
| Raw center crop | Sobel edge normalized, center 1536 | 8.0069 | 0.6056 | 0.3551 | medium |
| Raw center crop | Sobel edge normalized, center 1024 | 8.0022 | 0.7417 | 0.3232 | low |
| R39 reconstruction | brightness, full 2048 | 8.0247 | 0.0978 | 0.9549 | high |
| R39 reconstruction | high-pass brightness, full 2048 | 8.0247 | 0.0978 | 0.9549 | high |
| R39 reconstruction | Sobel edge raw magnitude, full 2048 | 8.0248 | 0.0903 | 0.9571 | high |
| R39 reconstruction | Sobel edge normalized, full 2048 | 8.0248 | 0.0903 | 0.9571 | high |
| R39 reconstruction | Sobel edge raw magnitude, center 1536 | 8.0228 | 0.0934 | 0.9675 | high |
| R39 reconstruction | Sobel edge raw magnitude, center 1024 | 8.0150 | 0.1017 | 0.9786 | high |
| R39 reconstruction | Sobel edge normalized, center 1536 | 8.0228 | 0.0934 | 0.9675 | high |
| R39 reconstruction | Sobel edge normalized, center 1024 | 8.0150 | 0.1017 | 0.9786 | high |
| v14 reconstruction | brightness, full 2048 | 8.0264 | 0.0979 | 0.9541 | high |
| v14 reconstruction | high-pass brightness, full 2048 | 8.0264 | 0.0979 | 0.9541 | high |
| v14 reconstruction | Sobel edge raw magnitude, full 2048 | 8.0246 | 0.0896 | 0.9583 | high |
| v14 reconstruction | Sobel edge normalized, full 2048 | 8.0246 | 0.0896 | 0.9583 | high |
| v14 reconstruction | Sobel edge raw magnitude, center 1536 | 8.0218 | 0.0925 | 0.9681 | high |
| v14 reconstruction | Sobel edge raw magnitude, center 1024 | 8.0135 | 0.1010 | 0.9784 | high |
| v14 reconstruction | Sobel edge normalized, center 1536 | 8.0218 | 0.0925 | 0.9681 | high |
| v14 reconstruction | Sobel edge normalized, center 1024 | 8.0135 | 0.1010 | 0.9784 | high |
| v16 reconstruction | brightness, full 2048 | 8.0260 | 0.0979 | 0.9544 | high |
| v16 reconstruction | high-pass brightness, full 2048 | 8.0260 | 0.0979 | 0.9544 | high |
| v16 reconstruction | Sobel edge raw magnitude, full 2048 | 8.0241 | 0.0900 | 0.9575 | high |
| v16 reconstruction | Sobel edge normalized, full 2048 | 8.0241 | 0.0900 | 0.9574 | high |
| v16 reconstruction | Sobel edge raw magnitude, center 1536 | 8.0212 | 0.0929 | 0.9677 | high |
| v16 reconstruction | Sobel edge raw magnitude, center 1024 | 8.0141 | 0.1013 | 0.9771 | high |
| v16 reconstruction | Sobel edge normalized, center 1536 | 8.0212 | 0.0929 | 0.9677 | high |
| v16 reconstruction | Sobel edge normalized, center 1024 | 8.0141 | 0.1013 | 0.9770 | high |

## Interpretation

- The brightness-only Raw result is low confidence because its response is low and it gives the wrong step scale.
- The Raw edge result recovers the expected scale, but it has a much larger large-error tail.
- The three reconstructions keep the expected scale and reduce step dx scatter by about 5.7x under the edge-based measurement.
- R39, v14, and v16 are effectively tied on this Step stability check; v14 has the smallest dx std by a tiny margin, while v16 has the smallest p95 absolute error by a tiny margin.

