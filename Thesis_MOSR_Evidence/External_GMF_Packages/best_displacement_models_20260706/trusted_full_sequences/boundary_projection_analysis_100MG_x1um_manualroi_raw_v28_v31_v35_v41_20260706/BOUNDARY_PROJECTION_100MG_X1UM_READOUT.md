# 100MG x 1um boundary projection readout

Fixed ROI: x=685, y=453, width=746, height=758 on 2048x1536 frames.
This ROI is the same manually selected 50x 1um ROI used in the prior thesis manual-run package and is reused for Raw, V28, V31, V35, and V41.

Object-plane pixel size: 0.069000 um/px. Nominal step: 1.000 um.
Scale note: this 20260702 100MG image sequence behaves as the 50x dataset used in the thesis manual-run package; 1 um is about 14.49 px in the image.

## Raw comparison

| selection | variant | steps | median step um | std um | median abs error um | std improvement vs Raw |
|---|---|---:|---:|---:|---:|---:|
| all_steps | raw | 49 | 1.005673 | 0.012895 | 0.009342 | +0.00% |
| all_steps | v28 | 49 | 1.005775 | 0.010722 | 0.008164 | +16.85% |
| all_steps | v31 | 49 | 1.005903 | 0.012117 | 0.009175 | +6.03% |
| all_steps | v35 | 49 | 1.005736 | 0.010737 | 0.008040 | +16.73% |
| all_steps | v41 | 49 | 1.005686 | 0.010734 | 0.008081 | +16.76% |
| common_best30 | raw | 30 | 1.003258 | 0.007418 | 0.006426 | +0.00% |
| common_best30 | v28 | 30 | 1.003191 | 0.005331 | 0.005314 | +28.13% |
| common_best30 | v31 | 30 | 1.003082 | 0.006479 | 0.006257 | +12.66% |
| common_best30 | v35 | 30 | 1.003208 | 0.005349 | 0.005424 | +27.90% |
| common_best30 | v41 | 30 | 1.003186 | 0.005346 | 0.005430 | +27.93% |
| own_best30_diagnostic | raw | 30 | 1.005484 | 0.005853 | 0.006426 | +0.00% |
| own_best30_diagnostic | v28 | 30 | 1.003191 | 0.005218 | 0.005314 | +10.84% |
| own_best30_diagnostic | v31 | 30 | 1.003513 | 0.006159 | 0.006257 | -5.23% |
| own_best30_diagnostic | v35 | 30 | 1.003208 | 0.005243 | 0.005424 | +10.42% |
| own_best30_diagnostic | v41 | 30 | 1.003186 | 0.005239 | 0.005430 | +10.48% |

## Common stable steps

The common stable set uses the same 30 step indices for every version.

4, 5, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 21, 23, 25, 26, 27, 29, 30, 33, 36, 38, 40, 41, 43, 45, 46, 47, 48

## Outputs

- boundary_projection_all_steps.csv: every consecutive step for every version.
- boundary_projection_summary.csv: all-step and filtered summaries.
- boundary_projection_raw_comparison.csv: direct comparison against Raw.
- boundary_projection_stable_steps.csv: selected stable-step measurements for every version.
- boundary_projection_common_step_diagnostics.csv: the shared stable-step selection and rejected unstable steps.
- fixed_roi_preview.png: ROI used for all versions.
