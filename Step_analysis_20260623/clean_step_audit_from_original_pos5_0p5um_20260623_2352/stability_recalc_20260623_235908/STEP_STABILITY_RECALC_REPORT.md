# Step Stability Recalculation Report

Generated: 2026-06-24T00:08:04

Calibration used: 2.5 um camera pixel / 20x objective = 0.125 um per image pixel.
Expected selected Step spacing: 0.5 um = 4 px.

## Main Result: Sobel Edge Full 2048

| case | step median dx px | step std dx px | step std um | 95% CI std px | p95 abs error um | median response | confidence | improvement vs raw |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| Raw center crop | 4.0126 | 1.0742 | 0.13427 | 0.9699-1.2126 | 0.42912 | 0.3478 | low | 1.00 |
| R39 reconstruction | 4.0038 | 0.1012 | 0.01265 | 0.0913-0.1142 | 0.02521 | 0.9580 | high | 10.62 |
| v14 reconstruction | 4.0040 | 0.1006 | 0.01258 | 0.0909-0.1136 | 0.02524 | 0.9587 | high | 10.67 |
| v16 reconstruction | 4.0042 | 0.1008 | 0.01260 | 0.0910-0.1138 | 0.02517 | 0.9585 | high | 10.66 |

## Same-Position Repeat Check

| case | repeat median mag px | repeat p95 mag px | repeat median mag um | median response | confidence |
|---|---:|---:|---:|---:|---|
| Raw center crop | 0.0293 | 0.0574 | 0.00367 | 0.3629 | medium |
| R39 reconstruction | 0.1138 | 0.2552 | 0.01423 | 0.9596 | high |
| v14 reconstruction | 0.1110 | 0.2544 | 0.01388 | 0.9605 | high |
| v16 reconstruction | 0.1130 | 0.2539 | 0.01413 | 0.9602 | high |

## Method Cross-Check: Step Scale

| case | method | median dx px | std dx px | median response | confidence |
|---|---|---:|---:|---:|---|
| Raw center crop | brightness, full 2048 | 0.4304 | 0.0226 | 0.2968 | low |
| Raw center crop | high-pass brightness, full 2048 | 0.4304 | 0.0226 | 0.2968 | low |
| Raw center crop | Sobel edge raw magnitude, full 2048 | 4.0126 | 1.0742 | 0.3478 | low |
| Raw center crop | Sobel edge normalized, full 2048 | 4.0126 | 1.0742 | 0.3478 | low |
| Raw center crop | Sobel edge raw magnitude, center 1536 | 4.0066 | 1.0406 | 0.3524 | low |
| Raw center crop | Sobel edge raw magnitude, center 1024 | 3.9907 | 1.4985 | 0.3208 | low |
| Raw center crop | Sobel edge normalized, center 1536 | 4.0066 | 1.0335 | 0.3527 | low |
| Raw center crop | Sobel edge normalized, center 1024 | 3.9908 | 1.4985 | 0.3209 | low |
| R39 reconstruction | brightness, full 2048 | 4.0025 | 0.1096 | 0.9579 | high |
| R39 reconstruction | high-pass brightness, full 2048 | 4.0025 | 0.1096 | 0.9579 | high |
| R39 reconstruction | Sobel edge raw magnitude, full 2048 | 4.0038 | 0.1012 | 0.9580 | high |
| R39 reconstruction | Sobel edge normalized, full 2048 | 4.0038 | 0.1012 | 0.9580 | high |
| R39 reconstruction | Sobel edge raw magnitude, center 1536 | 3.9989 | 0.1014 | 0.9672 | high |
| R39 reconstruction | Sobel edge raw magnitude, center 1024 | 4.0093 | 0.1066 | 0.9788 | high |
| R39 reconstruction | Sobel edge normalized, center 1536 | 3.9989 | 0.1014 | 0.9672 | high |
| R39 reconstruction | Sobel edge normalized, center 1024 | 4.0093 | 0.1066 | 0.9788 | high |
| v14 reconstruction | brightness, full 2048 | 4.0023 | 0.1096 | 0.9577 | high |
| v14 reconstruction | high-pass brightness, full 2048 | 4.0023 | 0.1096 | 0.9577 | high |
| v14 reconstruction | Sobel edge raw magnitude, full 2048 | 4.0040 | 0.1006 | 0.9587 | high |
| v14 reconstruction | Sobel edge normalized, full 2048 | 4.0040 | 0.1006 | 0.9587 | high |
| v14 reconstruction | Sobel edge raw magnitude, center 1536 | 4.0010 | 0.1010 | 0.9682 | high |
| v14 reconstruction | Sobel edge raw magnitude, center 1024 | 4.0087 | 0.1067 | 0.9784 | high |
| v14 reconstruction | Sobel edge normalized, center 1536 | 4.0010 | 0.1010 | 0.9682 | high |
| v14 reconstruction | Sobel edge normalized, center 1024 | 4.0087 | 0.1067 | 0.9784 | high |
| v16 reconstruction | brightness, full 2048 | 4.0025 | 0.1095 | 0.9578 | high |
| v16 reconstruction | high-pass brightness, full 2048 | 4.0026 | 0.1095 | 0.9578 | high |
| v16 reconstruction | Sobel edge raw magnitude, full 2048 | 4.0042 | 0.1008 | 0.9585 | high |
| v16 reconstruction | Sobel edge normalized, full 2048 | 4.0042 | 0.1008 | 0.9584 | high |
| v16 reconstruction | Sobel edge raw magnitude, center 1536 | 4.0002 | 0.1011 | 0.9675 | high |
| v16 reconstruction | Sobel edge raw magnitude, center 1024 | 4.0099 | 0.1066 | 0.9786 | high |
| v16 reconstruction | Sobel edge normalized, center 1536 | 4.0002 | 0.1011 | 0.9675 | high |
| v16 reconstruction | Sobel edge normalized, center 1024 | 4.0099 | 0.1066 | 0.9786 | high |

## Interpretation

- The brightness-only Raw result is low confidence because its response is low and it gives the wrong step scale.
- The Raw edge result recovers the expected scale, but it has a much larger large-error tail.
- The three reconstructions keep the expected scale and reduce step dx scatter by about 5.7x under the edge-based measurement.
- R39, v14, and v16 are effectively tied on this Step stability check; v14 has the smallest dx std by a tiny margin, while v16 has the smallest p95 absolute error by a tiny margin.

