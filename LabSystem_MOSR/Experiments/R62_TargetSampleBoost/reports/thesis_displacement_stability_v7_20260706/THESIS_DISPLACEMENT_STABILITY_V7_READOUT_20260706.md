# Thesis displacement stability validation - R62 V7 short candidate

## What was checked

- Reconstructed the six thesis displacement folders with the R62 V7 short candidate, PSF disabled/weak mode.
- Compared Raw, R61 v16, and R62 V7 with the same internal displacement checks.
- Used edge-phase as the main result, feature-corner as support, and gray DFT only as a sanity check because it can fail on repeated patterns.

## Main result: edge-phase, long time gaps removed

| group | best stability | Raw std um | R61 std um | V7 std um | V7 vs Raw | V7 vs R61 | Raw step um | R61 step um | V7 step um |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| x_1um | r61 | 0.00879 | 0.00763 | 0.00769 | -12.5% | 0.9% | 1.00798 | 1.00555 | 1.00558 |
| x_0p5um | r61 | 0.00618 | 0.00609 | 0.00624 | 1.0% | 2.5% | 0.50012 | 0.50068 | 0.50103 |
| 20x_1um | raw | 0.02208 | 0.02433 | 0.02432 | 10.1% | -0.1% | 1.01086 | 1.00973 | 1.00960 |
| 20x_0p5um | v7 | 0.03553 | 0.03552 | 0.03545 | -0.2% | -0.2% | 0.50185 | 0.49666 | 0.49646 |
| 5x_1um | r61 | 0.16278 | 0.13775 | 0.13806 | -15.2% | 0.2% | 1.00846 | 0.92687 | 0.92767 |
| 5x_0p5um | v7 | 0.01129 | 0.00954 | 0.00954 | -15.5% | -0.0% | 0.45383 | 0.49218 | 0.49160 |

## Cross-check status

| algorithm | groups usable | main issue |
|---|---:|---|
| edge_phase_primary | 6/6 | usable as main result |
| feature_corner_lk | 6/6 | usable as support, but optical-flow corners can be texture dependent |
| gray_dft_phase | 1/6 | fails on repeated 100MG dot pattern, so not used as main evidence |

## Plain conclusion

- V7 is not a dramatic improvement over R61 v16. In most groups it is almost identical to R61.
- Compared with Raw, the model helps stability in 100MG 1um, 5x 0.5um, and 5x 1um, but does not help 20x 1um and is basically neutral on 20x 0.5um.
- Compared with R61 v16, V7 is nearly unchanged. The current short V7 training has not yet produced a clearly stronger displacement model.
- Gray DFT should not be used as the thesis proof on repeated patterns; it can lock to the wrong repeated structure and report nearly zero motion.

## Files

- Main thesis table: main_edge_phase_thesis_table.csv
- All algorithm summary: all_algorithm_stability_summary.csv
- Algorithm comparison: algorithm_comparison_gap30.csv
- Main stability plot: edge_phase_gap30_stability_um.png
- Reconstructed-image manifest: r62_v7_seqgeom_reconstruction_summary_20260706.json in the R62 report folder
