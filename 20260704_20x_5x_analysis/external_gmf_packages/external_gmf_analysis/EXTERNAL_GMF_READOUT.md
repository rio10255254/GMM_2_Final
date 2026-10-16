# External GMF Readout - 20260704 20x/5x Package

## What Was Found

- Manifest cases: 36
- Cases with returned GMF_score.txt: 4
- Cases without returned score file: 32
- Important: the returned 20x files start at frame_0001, so the frame_0000 to frame_0001 interval is not available from external GMF.

## Returned Score Summary

| Case | Success rows | Step count | Expected px | Median abs(dx) px | Std abs(dx) px | Median abs(dy) px | Median score |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20x_1um_full_raw_input | 49/49 (100.0%) | 48 | 5.7971 | 5.8320 | 0.1483 | 0.0960 | 99.8882 |
| 20x_1um_full_r61_v16_psfoff | 49/49 (100.0%) | 48 | 5.7971 | 5.8210 | 0.1537 | 0.0925 | 99.6706 |
| 20x_0p5um_full_raw_input | 49/49 (100.0%) | 48 | 2.8986 | 2.9065 | 0.4481 | 0.0990 | 99.7390 |
| 20x_0p5um_full_r61_v16_psfoff | 49/49 (100.0%) | 48 | 2.8986 | 2.9040 | 0.4437 | 0.0955 | 99.7337 |

## Raw vs R61 v16 Comparison

| Group | Expected px | Raw median abs(dx) | R61 median abs(dx) | Raw std | R61 std | Std improvement | Raw median score | R61 median score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 20x_0p5um | 2.8986 | 2.9065 | 2.9040 | 0.4481 | 0.4437 | 1.0% | 99.7390 | 99.7337 |
| 20x_1um | 5.7971 | 5.8320 | 5.8210 | 0.1483 | 0.1537 | -3.7% | 99.8882 | 99.6706 |

## Sensitivity Check

| Case | Filter | Step count | Median abs(dx) px | Std abs(dx) px | Median abs(dy) px |
|---|---|---:|---:|---:|---:|
| 20x_0p5um_full_r61_v16_psfoff | all_steps | 48 | 2.9040 | 0.4437 | 0.0955 |
| 20x_0p5um_full_r61_v16_psfoff | remove_abs_dy_gt_1px | 46 | 2.9060 | 0.1701 | 0.0935 |
| 20x_0p5um_full_r61_v16_psfoff | plausible_x_motion_only | 47 | 2.9050 | 0.2110 | 0.0950 |
| 20x_0p5um_full_raw_input | all_steps | 48 | 2.9065 | 0.4481 | 0.0990 |
| 20x_0p5um_full_raw_input | remove_abs_dy_gt_1px | 46 | 2.9110 | 0.1691 | 0.0970 |
| 20x_0p5um_full_raw_input | plausible_x_motion_only | 47 | 2.9100 | 0.2122 | 0.0970 |
| 20x_1um_full_r61_v16_psfoff | all_steps | 48 | 5.8210 | 0.1537 | 0.0925 |
| 20x_1um_full_r61_v16_psfoff | remove_abs_dy_gt_1px | 47 | 5.8260 | 0.1157 | 0.0860 |
| 20x_1um_full_r61_v16_psfoff | plausible_x_motion_only | 48 | 5.8210 | 0.1537 | 0.0925 |
| 20x_1um_full_raw_input | all_steps | 48 | 5.8320 | 0.1483 | 0.0960 |
| 20x_1um_full_raw_input | remove_abs_dy_gt_1px | 47 | 5.8320 | 0.1139 | 0.0930 |
| 20x_1um_full_raw_input | plausible_x_motion_only | 48 | 5.8320 | 0.1483 | 0.0960 |

## Main Anomalous Steps

| Case | Frame step | dx px | dy px | abs(dx) error px | Reason |
|---|---:|---:|---:|---:|---|
| 20x_0p5um_full_raw_input | 14->15 | -0.1400 | -3.3750 | 2.7586 | not plausible x step, large y step, large x error |
| 20x_0p5um_full_raw_input | 44->45 | -2.0260 | -1.2070 | 0.8726 | large y step, large x error |
| 20x_0p5um_full_raw_input | 45->46 | -3.6600 | 0.9220 | 0.7614 | large x error |
| 20x_0p5um_full_raw_input | 12->13 | -3.4030 | 0.6110 | 0.5044 | large x error |
| 20x_0p5um_full_r61_v16_psfoff | 14->15 | -0.1700 | -3.2900 | 2.7286 | not plausible x step, large y step, large x error |
| 20x_0p5um_full_r61_v16_psfoff | 44->45 | -2.0470 | -1.2930 | 0.8516 | large y step, large x error |
| 20x_0p5um_full_r61_v16_psfoff | 45->46 | -3.6370 | 0.9500 | 0.7384 | large x error |
| 20x_0p5um_full_r61_v16_psfoff | 12->13 | -3.4260 | 0.5790 | 0.5274 | large x error |
| 20x_1um_full_raw_input | 41->42 | -5.1560 | -1.0230 | 0.6411 | large y step, large x error |
| 20x_1um_full_r61_v16_psfoff | 41->42 | -5.1140 | -1.0020 | 0.6831 | large y step, large x error |
| 20x_1um_full_r61_v16_psfoff | 7->8 | -6.2980 | 0.5690 | 0.5009 | large x error |

## Missing Returned Scores

- 5x_1um_full_raw_input
- 5x_1um_full_r61_v16_psfoff
- 5x_0p5um_full_raw_input
- 5x_0p5um_full_r61_v16_psfoff
- 20x_1um_seg00_frames000_002_raw_input
- 20x_1um_seg00_frames000_002_r61_v16_psfoff
- 20x_1um_seg01_frames003_049_raw_input
- 20x_1um_seg01_frames003_049_r61_v16_psfoff
- 20x_0p5um_seg00_frames000_014_raw_input
- 20x_0p5um_seg00_frames000_014_r61_v16_psfoff
- 20x_0p5um_seg01_frames015_049_raw_input
- 20x_0p5um_seg01_frames015_049_r61_v16_psfoff
- 5x_1um_seg00_frames000_008_raw_input
- 5x_1um_seg00_frames000_008_r61_v16_psfoff
- 5x_1um_seg01_frames009_010_raw_input
- 5x_1um_seg01_frames009_010_r61_v16_psfoff
- 5x_1um_seg02_frames013_017_raw_input
- 5x_1um_seg02_frames013_017_r61_v16_psfoff
- 5x_1um_seg03_frames018_019_raw_input
- 5x_1um_seg03_frames018_019_r61_v16_psfoff
- 5x_1um_seg04_frames020_049_raw_input
- 5x_1um_seg04_frames020_049_r61_v16_psfoff
- 5x_0p5um_seg00_frames000_006_raw_input
- 5x_0p5um_seg00_frames000_006_r61_v16_psfoff
- 5x_0p5um_seg01_frames007_027_raw_input
- 5x_0p5um_seg01_frames007_027_r61_v16_psfoff
- 5x_0p5um_seg02_frames028_029_raw_input
- 5x_0p5um_seg02_frames028_029_r61_v16_psfoff
- 5x_0p5um_seg03_frames030_033_raw_input
- 5x_0p5um_seg03_frames030_033_r61_v16_psfoff
- 5x_0p5um_seg04_frames034_049_raw_input
- 5x_0p5um_seg04_frames034_049_r61_v16_psfoff

## Output Files

- external_gmf_rows.csv: parsed GMF positions
- external_gmf_consecutive_steps.csv: frame-to-frame displacement table
- external_gmf_summary.csv: per-case readout
- external_gmf_raw_vs_v16_comparison.csv: Raw/R61 comparison
- external_gmf_sensitivity_summary.csv: same metrics after removing obvious large-y jumps
- external_gmf_anomalous_steps.csv: steps that deserve manual inspection
- external_gmf_20x_step_traces.png: displacement trace plot
- external_gmf_20x_summary.png: median displacement summary plot
