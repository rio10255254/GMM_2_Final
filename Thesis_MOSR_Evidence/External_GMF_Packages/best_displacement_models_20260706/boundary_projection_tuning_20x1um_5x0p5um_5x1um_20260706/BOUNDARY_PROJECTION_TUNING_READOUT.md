# Boundary projection tuning readout

Groups: 20x_1um and 5x_0p5um from trusted_full_sequences; 5x_1um from all_sequences as a diagnostic group.
Variants: Raw, V28, V31, V35, V41.

## Group setup

| group | source status | nominal step um | pixel size um/px | expected px/step | base ROI | prior manual median um | prior manual std um |
|---|---|---:|---:|---:|---|---:|---:|
| 20x_1um | trusted | 1.000 | 0.172500 | 5.797101 | 260,607,504,528 | 1.003950 | 0.024259 |
| 5x_0p5um | trusted | 0.500 | 0.690000 | 0.724638 | 964,454,725,725 | 0.517500 | 0.008753 |
| 5x_1um | diagnostic all_sequences | 1.000 | 0.690000 | 1.449275 | 960,454,721,725 | 0.910800 | 0.137972 |

## Best method per group, Raw-anchor stable 30 steps

Raw-anchor means the 30 step indices are selected using Raw only, then every model is evaluated on those same steps.

| group | best model | method | Raw std um | model std um | improvement | model median error um |
|---|---|---|---:|---:|---:|---:|
| 20x_1um | v31 | roi90_mag_sigma1p2_phase_guarded | 0.005769 | 0.005994 | -3.91% | 0.005175 |
| 5x_0p5um | v31 | roi90_mag_sigma0p8_phase_guarded | 0.005236 | 0.005236 | +0.00% | 0.003700 |
| 5x_1um | v31 | roi100_mag_sigma0p8_phase_guarded | 0.060731 | 0.055513 | +8.59% | 0.065050 |

## Fair Raw-only method check

This chooses the method with the lowest Raw std inside each group, then reports the best model under that same method.

| group | Raw-selected method | Raw std um | best model | model std um | improvement |
|---|---|---:|---|---:|---:|
| 20x_1um | roi90_gx_abs_sigma0p8_phase_guarded | 0.005682 | v31 | 0.006151 | -8.25% |
| 5x_0p5um | roi90_mag_sigma0p8_phase_guarded | 0.005236 | v31 | 0.005236 | +0.00% |
| 5x_1um | roi100_mag_sigma0p8_phase_guarded | 0.060731 | v31 | 0.055513 | +8.59% |

## Outputs

- tuning_all_steps.csv: every measurement under every tested method.
- tuning_summary.csv: all-step and filtered summaries.
- tuning_raw_comparison.csv: model-vs-Raw comparison.
- tuning_method_rankings.csv: method-level ranking and best model under each method.
- roi_tuning_preview_*.png: ROI scale previews.
- top_methods_raw_anchor_*.png: top candidate method charts.
