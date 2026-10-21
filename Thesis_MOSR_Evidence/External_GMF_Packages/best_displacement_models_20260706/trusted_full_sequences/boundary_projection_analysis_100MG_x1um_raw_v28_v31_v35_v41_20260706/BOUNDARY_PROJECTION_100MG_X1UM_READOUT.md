# 100MG x 1um boundary projection readout

Fixed ROI: x=1010, y=35, width=900, height=650 on 2048x1536 frames.
This ROI covers the upper-right boundary-rich pillar array and is reused for Raw, V28, V31, V35, and V41.

Object-plane pixel size: 0.069000 um/px. Nominal step: 1.000 um.
Scale note: this 20260702 100MG image sequence behaves as the 50x dataset used in the thesis manual-run package; 1 um is about 14.49 px in the image.

## Raw comparison

| selection | variant | steps | median step um | std um | median abs error um | std improvement vs Raw |
|---|---|---:|---:|---:|---:|---:|
| all_steps | raw | 49 | 1.003415 | 0.009529 | 0.005067 | +0.00% |
| all_steps | v28 | 49 | 1.003768 | 0.009673 | 0.005110 | -1.51% |
| all_steps | v31 | 49 | 1.003361 | 0.009543 | 0.005237 | -0.15% |
| all_steps | v35 | 49 | 1.003806 | 0.009664 | 0.005106 | -1.42% |
| all_steps | v41 | 49 | 1.003805 | 0.009661 | 0.005048 | -1.39% |
| common_best30 | raw | 30 | 1.002009 | 0.002797 | 0.002801 | +0.00% |
| common_best30 | v28 | 30 | 1.002469 | 0.002868 | 0.002851 | -2.56% |
| common_best30 | v31 | 30 | 1.002341 | 0.002855 | 0.002887 | -2.09% |
| common_best30 | v35 | 30 | 1.002485 | 0.002882 | 0.002842 | -3.06% |
| common_best30 | v41 | 30 | 1.002445 | 0.002873 | 0.002867 | -2.71% |
| own_best30_diagnostic | raw | 30 | 1.001703 | 0.003008 | 0.002801 | +0.00% |
| own_best30_diagnostic | v28 | 30 | 1.002469 | 0.002785 | 0.002851 | +7.40% |
| own_best30_diagnostic | v31 | 30 | 1.001990 | 0.003049 | 0.002887 | -1.38% |
| own_best30_diagnostic | v35 | 30 | 1.002485 | 0.002792 | 0.002842 | +7.17% |
| own_best30_diagnostic | v41 | 30 | 1.002445 | 0.002785 | 0.002867 | +7.42% |

## Common stable steps

The common stable set uses the same 30 step indices for every version.

4, 7, 9, 10, 11, 13, 14, 17, 21, 22, 23, 24, 25, 26, 27, 29, 30, 33, 34, 35, 37, 38, 39, 40, 42, 43, 44, 47, 48, 49

## Outputs

- boundary_projection_all_steps.csv: every consecutive step for every version.
- boundary_projection_summary.csv: all-step and filtered summaries.
- boundary_projection_raw_comparison.csv: direct comparison against Raw.
- boundary_projection_stable_steps.csv: selected stable steps and per-step diagnostics.
- fixed_roi_preview.png: ROI used for all versions.
