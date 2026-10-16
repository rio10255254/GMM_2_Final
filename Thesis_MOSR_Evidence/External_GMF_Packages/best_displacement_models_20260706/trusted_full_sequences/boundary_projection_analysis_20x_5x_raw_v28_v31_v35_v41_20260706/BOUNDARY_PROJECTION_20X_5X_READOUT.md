# 20x and 5x boundary projection readout

Compared cases: Raw, V28, V31, V35, V41.
Method: fixed manual ROI, boundary projection profile matching, and the same common stable 30 steps inside each group.

## Available groups

| group | nominal step um | pixel size um/px | expected px/step | ROI x,y,w,h |
|---|---:|---:|---:|---|
| 20x_0p5um | 0.500 | 0.172500 | 2.898551 | 259,607,494,473 |
| 20x_1um | 1.000 | 0.172500 | 5.797101 | 260,607,504,528 |
| 5x_0p5um | 0.500 | 0.690000 | 0.724638 | 964,454,725,725 |

Note: 5x_1um had a manual ROI record, but it is not present in this trusted full-sequence package.

## Raw comparison

| group | selection | variant | steps | median step um | std um | median abs error um | std improvement vs Raw | mean x corr |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 20x_0p5um | all_steps | raw | 49 | 0.501524 | 0.080227 | 0.009720 | +0.00% | 0.9970 |
| 20x_0p5um | all_steps | v28 | 49 | 0.503703 | 0.080395 | 0.008501 | -0.21% | 0.9797 |
| 20x_0p5um | all_steps | v31 | 49 | 0.501887 | 0.080252 | 0.009200 | -0.03% | 0.9930 |
| 20x_0p5um | all_steps | v35 | 49 | 0.503583 | 0.080392 | 0.008360 | -0.21% | 0.9799 |
| 20x_0p5um | all_steps | v41 | 49 | 0.503587 | 0.080392 | 0.008288 | -0.21% | 0.9798 |
| 20x_0p5um | common_best30 | raw | 30 | 0.500405 | 0.006694 | 0.004320 | +0.00% | 0.9983 |
| 20x_0p5um | common_best30 | v28 | 30 | 0.502594 | 0.005959 | 0.004770 | +10.98% | 0.9833 |
| 20x_0p5um | common_best30 | v31 | 30 | 0.501491 | 0.006217 | 0.004230 | +7.13% | 0.9951 |
| 20x_0p5um | common_best30 | v35 | 30 | 0.502454 | 0.005959 | 0.004653 | +10.98% | 0.9835 |
| 20x_0p5um | common_best30 | v41 | 30 | 0.502485 | 0.005949 | 0.004643 | +11.13% | 0.9833 |
| 20x_0p5um | own_best30_diagnostic | raw | 30 | 0.500405 | 0.006694 | 0.004320 | +0.00% | 0.9983 |
| 20x_0p5um | own_best30_diagnostic | v28 | 30 | 0.502594 | 0.005959 | 0.004770 | +10.98% | 0.9833 |
| 20x_0p5um | own_best30_diagnostic | v31 | 30 | 0.501491 | 0.006217 | 0.004230 | +7.13% | 0.9951 |
| 20x_0p5um | own_best30_diagnostic | v35 | 30 | 0.502454 | 0.005959 | 0.004653 | +10.98% | 0.9835 |
| 20x_0p5um | own_best30_diagnostic | v41 | 30 | 0.502485 | 0.005949 | 0.004643 | +11.13% | 0.9833 |
| 20x_1um | all_steps | raw | 49 | 1.005656 | 0.025658 | 0.008743 | +0.00% | 0.9940 |
| 20x_1um | all_steps | v28 | 49 | 1.009089 | 0.025104 | 0.010771 | +2.16% | 0.9592 |
| 20x_1um | all_steps | v31 | 49 | 1.006621 | 0.025398 | 0.009331 | +1.01% | 0.9859 |
| 20x_1um | all_steps | v35 | 49 | 1.009084 | 0.025118 | 0.010720 | +2.11% | 0.9597 |
| 20x_1um | all_steps | v41 | 49 | 1.009039 | 0.025113 | 0.010663 | +2.13% | 0.9594 |
| 20x_1um | common_best30 | raw | 30 | 1.003226 | 0.006539 | 0.005525 | +0.00% | 0.9939 |
| 20x_1um | common_best30 | v28 | 30 | 1.007261 | 0.006895 | 0.007552 | -5.45% | 0.9585 |
| 20x_1um | common_best30 | v31 | 30 | 1.005237 | 0.006530 | 0.006335 | +0.14% | 0.9856 |
| 20x_1um | common_best30 | v35 | 30 | 1.007044 | 0.006792 | 0.007600 | -3.87% | 0.9589 |
| 20x_1um | common_best30 | v41 | 30 | 1.007028 | 0.006767 | 0.007666 | -3.49% | 0.9586 |
| 20x_1um | own_best30_diagnostic | raw | 30 | 1.003226 | 0.006043 | 0.005525 | +0.00% | 0.9939 |
| 20x_1um | own_best30_diagnostic | v28 | 30 | 1.003629 | 0.007703 | 0.007552 | -27.48% | 0.9564 |
| 20x_1um | own_best30_diagnostic | v31 | 30 | 1.005237 | 0.006308 | 0.006335 | -4.39% | 0.9858 |
| 20x_1um | own_best30_diagnostic | v35 | 30 | 1.003822 | 0.007596 | 0.007600 | -25.72% | 0.9569 |
| 20x_1um | own_best30_diagnostic | v41 | 30 | 1.003891 | 0.007555 | 0.007666 | -25.03% | 0.9566 |
| 5x_0p5um | all_steps | raw | 49 | 0.542948 | 0.011358 | 0.042948 | +0.00% | 0.9214 |
| 5x_0p5um | all_steps | v28 | 49 | 0.541849 | 0.011925 | 0.041849 | -4.99% | 0.9267 |
| 5x_0p5um | all_steps | v31 | 49 | 0.543233 | 0.011432 | 0.043233 | -0.65% | 0.9190 |
| 5x_0p5um | all_steps | v35 | 49 | 0.541903 | 0.011902 | 0.041903 | -4.80% | 0.9265 |
| 5x_0p5um | all_steps | v41 | 49 | 0.541919 | 0.011928 | 0.041919 | -5.02% | 0.9268 |
| 5x_0p5um | common_best30 | raw | 30 | 0.539456 | 0.006490 | 0.039456 | +0.00% | 0.9159 |
| 5x_0p5um | common_best30 | v28 | 30 | 0.536765 | 0.006775 | 0.036765 | -4.40% | 0.9215 |
| 5x_0p5um | common_best30 | v31 | 30 | 0.539635 | 0.006526 | 0.039635 | -0.55% | 0.9132 |
| 5x_0p5um | common_best30 | v35 | 30 | 0.536869 | 0.006780 | 0.036869 | -4.47% | 0.9214 |
| 5x_0p5um | common_best30 | v41 | 30 | 0.536847 | 0.006795 | 0.036847 | -4.70% | 0.9217 |
| 5x_0p5um | own_best30_diagnostic | raw | 30 | 0.539456 | 0.006428 | 0.039456 | +0.00% | 0.9158 |
| 5x_0p5um | own_best30_diagnostic | v28 | 30 | 0.536765 | 0.006764 | 0.036765 | -5.23% | 0.9215 |
| 5x_0p5um | own_best30_diagnostic | v31 | 30 | 0.539635 | 0.006506 | 0.039635 | -1.21% | 0.9132 |
| 5x_0p5um | own_best30_diagnostic | v35 | 30 | 0.536869 | 0.006769 | 0.036869 | -5.30% | 0.9213 |
| 5x_0p5um | own_best30_diagnostic | v41 | 30 | 0.536847 | 0.006790 | 0.036847 | -5.63% | 0.9217 |

## Common stable steps

- 20x_0p5um: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 21, 22, 23, 24, 25, 26, 27, 30, 31, 32, 33, 35, 37, 38, 40, 41, 43, 44, 48
- 20x_1um: 1, 2, 6, 9, 10, 11, 13, 15, 17, 19, 21, 23, 24, 25, 27, 28, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 45, 46, 48, 49
- 5x_0p5um: 1, 2, 3, 6, 9, 11, 12, 14, 15, 16, 17, 20, 22, 24, 25, 27, 28, 31, 33, 35, 36, 38, 39, 41, 42, 43, 45, 46, 47, 49

## Direction check

| group | candidate signed dx px | median step first15 um | median abs error first15 um | std first15 um | mean corr first15 |
|---|---:|---:|---:|---:|---:|
| 20x_0p5um | -2.898551 | 0.501461 | 0.008010 | 0.133545 | 0.9975 |
| 20x_0p5um | 2.898551 | 0.000000 | 0.500000 | 0.000000 | 0.4576 |
| 20x_1um | -5.797101 | 1.002835 | 0.009585 | 0.030056 | 0.9936 |
| 20x_1um | 5.797101 | 0.850814 | 0.149186 | 0.030755 | -0.0015 |
| 5x_0p5um | -0.724638 | 0.543955 | 0.043955 | 0.013260 | 0.9219 |
| 5x_0p5um | 0.724638 | 0.690000 | 0.190000 | 0.000000 | 0.9219 |

## Outputs

- boundary_projection_all_steps.csv: every consecutive step for every available group and version.
- boundary_projection_summary.csv: all-step, common stable-step, and diagnostic filtered summaries.
- boundary_projection_raw_comparison.csv: direct comparison against Raw inside each group.
- boundary_projection_stable_steps.csv: selected stable-step measurements.
- boundary_projection_common_step_diagnostics.csv: selected and rejected step diagnostics.
- fixed_roi_preview_*.png: the ROI used in each group.
- boundary_projection_step_trace_*.png: step-by-step measured displacement traces.
- boundary_projection_*_ranking.png: stability and accuracy ranking charts.
