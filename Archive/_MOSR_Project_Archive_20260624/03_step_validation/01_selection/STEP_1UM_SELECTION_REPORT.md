# Step 1um selection report

Generated: 2026-06-23T17:35:21

Source: `Step`

Image count: 788 BMP, interpreted as 394 positions with 2 captures per position.

User calibration: 2.5 um camera pixel / 20x objective = 0.125000 um/px.
Expected motion: 0.1 um = 0.800 px, 1.0 um = 8.000 px.

Measured with central ROI phase correlation.

## Measured raw behavior

| check | count | median dx px | median dy px | median mag px | p95 mag px | median response |
|---|---:|---:|---:|---:|---:|---:|
| same-position replicate pair | 394 | -0.001102 | -0.000527 | 0.018823 | 0.043086 | 0.445912 |
| adjacent 0.1 um same-replicate pair | 786 | 0.084245 | -0.002440 | 0.085740 | 0.112969 | 0.438471 |
| selected 1.0 um pair, positions +10 | 78 | 0.742537 | -0.047712 | 0.742768 | 0.837255 | 0.088336 |
| all sliding 1.0 um probe, positions +10 | 768 | 0.728810 | -0.038589 | 0.732582 | 0.841209 | 0.088085 |

## Selected 1um sequence

Use positions `0, 10, 20, ..., 390`. This gives 40 selected positions, or 39 one-micron steps per replicate sequence. Use both replicate streams as two independent 1um sequences:

- replicate 0: image indices 0, 20, 40, ..., 780
- replicate 1: image indices 1, 21, 41, ..., 781

The remaining final positions after 390 are intentionally not used, because they do not complete another 1um interval.

Selection manifest: `Analyses/Step_analysis_20260623/selected_1um_positions.csv`
Pair manifest: `Analyses/Step_analysis_20260623/selected_1um_pairs.csv`

## Important caveat

The file ordering strongly supports two captures per position, but the measured image motion is much smaller than the user-calibrated expectation of 8 px per 1 um. The selected pairs are therefore 1 um by commanded position index, not by observed pixel magnitude.
