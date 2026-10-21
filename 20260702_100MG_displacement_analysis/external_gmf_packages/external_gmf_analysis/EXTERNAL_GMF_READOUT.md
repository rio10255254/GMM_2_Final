# External GMF Returned-Score Readout

## Package Status

| package | manifest cases | score files found |
|---|---:|---:|
| full_sequences | 4 | 4 |
| stable_segments | 8 | 0 |

## Case Summary

| case | rows | success rows | success rate | median successful score | consecutive success steps | plausible x-motion steps |
|---|---:|---:|---:|---:|---:|---:|
| x_1um_raw_input | 49 | 49 | 100.0% | 97.974 | 48 | 48 |
| x_1um_r61_v16_psfoff | 49 | 49 | 100.0% | 98.954 | 48 | 48 |
| x_0p5um_raw_input | 50 | 50 | 100.0% | 98.645 | 49 | 48 |
| x_0p5um_r61_v16_psfoff | 50 | 50 | 100.0% | 98.912 | 49 | 48 |
| x_1um_segA_frames001_005_raw_input | missing | missing | NA | NA | 0 | 0 |
| x_1um_segA_frames001_005_r61_v16_psfoff | missing | missing | NA | NA | 0 | 0 |
| x_1um_segB_frames006_049_raw_input | missing | missing | NA | NA | 0 | 0 |
| x_1um_segB_frames006_049_r61_v16_psfoff | missing | missing | NA | NA | 0 | 0 |
| x_0p5um_segA_frames000_026_raw_input | missing | missing | NA | NA | 0 | 0 |
| x_0p5um_segA_frames000_026_r61_v16_psfoff | missing | missing | NA | NA | 0 | 0 |
| x_0p5um_segB_frames031_050_raw_input | missing | missing | NA | NA | 0 | 0 |
| x_0p5um_segB_frames031_050_r61_v16_psfoff | missing | missing | NA | NA | 0 | 0 |

## Raw vs R61 v16

| dataset | nominal step | Raw success | v16 success | gain | multiplier | Raw plausible steps | v16 plausible steps |
|---|---:|---:|---:|---:|---:|---:|---:|
| x_0p5um | 0.5 um | 100.0% | 100.0% | 0.0 pp | 1.00x | 48 | 48 |
| x_1um | 1.0 um | 100.0% | 100.0% | 0.0 pp | 1.00x | 48 | 48 |

## Displacement Stability

| case | filter | steps | median abs dx | std abs dx | median abs dy | excluded steps |
|---|---|---:|---:|---:|---:|---:|
| x_0p5um_r61_v16_psfoff | all_steps | 49 | 7.2610 | 0.7616 | 0.0590 | 0 |
| x_0p5um_r61_v16_psfoff | plausible_only | 48 | 7.2605 | 0.1795 | 0.0570 | 1 |
| x_0p5um_raw_input | all_steps | 49 | 7.2700 | 0.7622 | 0.0670 | 0 |
| x_0p5um_raw_input | plausible_only | 48 | 7.2670 | 0.1825 | 0.0650 | 1 |
| x_1um_r61_v16_psfoff | all_steps | 48 | 14.5560 | 0.1099 | 0.0655 | 0 |
| x_1um_r61_v16_psfoff | plausible_only | 48 | 14.5560 | 0.1099 | 0.0655 | 0 |
| x_1um_raw_input | all_steps | 48 | 14.5435 | 0.1210 | 0.0720 | 0 |
| x_1um_raw_input | plausible_only | 48 | 14.5435 | 0.1210 | 0.0720 | 0 |

## Interpretation Guard

- A row is counted as a successful GMF row only when Score0, scale, and position are non-zero.
- A plausible x-motion step requires two adjacent frames to both be successful and the x shift to match the expected direction/magnitude band.
- The stable-segment package is reported separately because it needs its own returned score files.
