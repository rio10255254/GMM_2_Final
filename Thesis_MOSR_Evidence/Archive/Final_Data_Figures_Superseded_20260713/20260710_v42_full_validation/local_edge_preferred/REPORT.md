# V42 preferred local-edge displacement validation

This package uses the optimized local boundary method with subpixel localization, repeated-pattern mismatch rejection, and multi-edge consensus.

The main display mode follows the established thesis protocol: one shared set of local edge positions is detected from the frozen V41 reference and then applied unchanged to Raw, V41, and V42. Independent self-detected and V42-guided modes are retained as controls.

## All valid acquisition steps

| Dataset         |   Raw SD (nm) |   V41 SD (nm) |   V42 SD (nm) |   V42 SD improvement vs Raw (%) |   Raw total uncertainty (nm) |   V42 total uncertainty (nm) |   V42 total improvement vs Raw (%) |
|:----------------|--------------:|--------------:|--------------:|--------------------------------:|-----------------------------:|-----------------------------:|-----------------------------------:|
| 50x 0.5 um/step |         36.64 |         34.95 |         33.91 |                            7.47 |                       221.80 |                        99.53 |                              55.13 |
| 50x 1 um/step   |         33.09 |         32.01 |         21.87 |                           33.92 |                       479.14 |                       206.21 |                              56.96 |
| 20x 0.5 um/step |         37.76 |         43.12 |         40.47 |                           -7.18 |                       204.99 |                       293.06 |                             -42.97 |
| 20x 1 um/step   |         52.38 |         38.00 |         90.87 |                          -73.47 |                       183.97 |                       137.06 |                              25.50 |
| 5x 0.5 um/step  |         11.71 |         12.85 |         11.33 |                            3.27 |                       470.40 |                       328.37 |                              30.19 |
| 5x 1 um/step    |        167.76 |        164.62 |        170.48 |                           -1.62 |                       503.01 |                       373.95 |                              25.66 |

## Common best 30 steps

| Dataset         |   Raw SD (nm) |   V41 SD (nm) |   V42 SD (nm) |   V42 SD improvement vs Raw (%) |   Raw total uncertainty (nm) |   V42 total uncertainty (nm) |   V42 total improvement vs Raw (%) |
|:----------------|--------------:|--------------:|--------------:|--------------------------------:|-----------------------------:|-----------------------------:|-----------------------------------:|
| 50x 0.5 um/step |         27.92 |         25.44 |         23.78 |                           14.82 |                       217.24 |                        94.97 |                              56.28 |
| 50x 1 um/step   |         32.19 |         32.73 |         22.01 |                           31.61 |                       478.12 |                       212.22 |                              55.61 |
| 20x 0.5 um/step |         20.70 |         27.17 |         16.04 |                           22.51 |                       203.82 |                       307.46 |                             -50.85 |
| 20x 1 um/step   |         51.45 |         31.92 |         82.18 |                          -59.74 |                       185.91 |                       130.20 |                              29.96 |
| 5x 0.5 um/step  |          9.02 |          9.65 |          9.35 |                           -3.67 |                       474.73 |                       328.52 |                              30.80 |
| 5x 1 um/step    |         61.93 |         60.93 |         64.33 |                           -3.88 |                       491.27 |                       343.61 |                              30.06 |

## Raw-anchored best 30 steps

| Dataset         |   Raw SD (nm) |   V41 SD (nm) |   V42 SD (nm) |   V42 SD improvement vs Raw (%) |   Raw total uncertainty (nm) |   V42 total uncertainty (nm) |   V42 total improvement vs Raw (%) |
|:----------------|--------------:|--------------:|--------------:|--------------------------------:|-----------------------------:|-----------------------------:|-----------------------------------:|
| 50x 0.5 um/step |         27.82 |         25.23 |         23.84 |                           14.32 |                       217.23 |                        95.39 |                              56.09 |
| 50x 1 um/step   |         39.81 |         35.79 |         24.02 |                           39.65 |                       479.92 |                       212.44 |                              55.74 |
| 20x 0.5 um/step |         20.70 |         27.17 |         16.04 |                           22.51 |                       203.82 |                       307.46 |                             -50.85 |
| 20x 1 um/step   |         51.47 |         33.72 |         82.14 |                          -59.58 |                       185.92 |                       130.18 |                              29.98 |
| 5x 0.5 um/step  |          8.79 |          9.75 |          9.37 |                           -6.69 |                       477.05 |                       328.52 |                              31.14 |
| 5x 1 um/step    |         61.93 |         60.93 |         64.33 |                           -3.88 |                       491.27 |                       343.61 |                              30.06 |

## Validation notes

- Source acquisition steps: 295
- Every reported step is case symmetric: Raw, V41, and V42 use the same frame pair and ROI.
- Frozen-V41-guided shared edges are the primary thesis display because this was the established protocol before V42 was evaluated.
- V42-guided and independent self-detected edges are retained as supplementary controls.
- Total uncertainty is the root-sum-square of step repeatability SD and median boundary-localization uncertainty.

## Valid measurement counts

| selection         | edge_mode                   | case           |   sum |   count |
|:------------------|:----------------------------|:---------------|------:|--------:|
| all_steps         | self_detected_edges         | raw            |   294 |     295 |
| all_steps         | self_detected_edges         | v41_standalone |   294 |     295 |
| all_steps         | self_detected_edges         | v42_e120       |   290 |     295 |
| all_steps         | v41_standalone_guided_edges | raw            |   294 |     295 |
| all_steps         | v41_standalone_guided_edges | v41_standalone |   294 |     295 |
| all_steps         | v41_standalone_guided_edges | v42_e120       |   294 |     295 |
| all_steps         | v42_e120_guided_edges       | raw            |   294 |     295 |
| all_steps         | v42_e120_guided_edges       | v41_standalone |   294 |     295 |
| all_steps         | v42_e120_guided_edges       | v42_e120       |   290 |     295 |
| common_best30     | self_detected_edges         | raw            |   180 |     180 |
| common_best30     | self_detected_edges         | v41_standalone |   180 |     180 |
| common_best30     | self_detected_edges         | v42_e120       |   177 |     180 |
| common_best30     | v41_standalone_guided_edges | raw            |   180 |     180 |
| common_best30     | v41_standalone_guided_edges | v41_standalone |   180 |     180 |
| common_best30     | v41_standalone_guided_edges | v42_e120       |   180 |     180 |
| common_best30     | v42_e120_guided_edges       | raw            |   180 |     180 |
| common_best30     | v42_e120_guided_edges       | v41_standalone |   180 |     180 |
| common_best30     | v42_e120_guided_edges       | v42_e120       |   177 |     180 |
| raw_anchor_best30 | self_detected_edges         | raw            |   180 |     180 |
| raw_anchor_best30 | self_detected_edges         | v41_standalone |   180 |     180 |
| raw_anchor_best30 | self_detected_edges         | v42_e120       |   177 |     180 |
| raw_anchor_best30 | v41_standalone_guided_edges | raw            |   180 |     180 |
| raw_anchor_best30 | v41_standalone_guided_edges | v41_standalone |   180 |     180 |
| raw_anchor_best30 | v41_standalone_guided_edges | v42_e120       |   180 |     180 |
| raw_anchor_best30 | v42_e120_guided_edges       | raw            |   180 |     180 |
| raw_anchor_best30 | v42_e120_guided_edges       | v41_standalone |   180 |     180 |
| raw_anchor_best30 | v42_e120_guided_edges       | v42_e120       |   177 |     180 |