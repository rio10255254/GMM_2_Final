# Uncertainty-aware displacement readout

This readout keeps the same measured step values, but reports displacement as a metrology readout:

`total uncertainty = sqrt(step repeatability SD^2 + boundary localization uncertainty^2)`

The purpose is to include the fact that a clearer reconstructed boundary is easier to localize, even when the raw pairwise step SD is accidentally small.

## Preferred thesis table: Raw vs V41-Standalone

| Dataset         |   Raw step SD (nm) |   V41 step SD (nm) |   Raw edge uncertainty (nm) |   V41 edge uncertainty (nm) |   Raw total (nm) |   V41 total (nm) |   Improvement (%) |   Boundary confidence ratio |
|:----------------|-------------------:|-------------------:|----------------------------:|----------------------------:|-----------------:|-----------------:|------------------:|----------------------------:|
| 50x 0.5 um/step |              28.79 |              25.3  |                      218.79 |                      103.94 |           220.67 |           106.97 |             51.53 |                        3.3  |
| 50x 1 um/step   |              31.28 |              31.8  |                      477.03 |                      254.22 |           478.06 |           256.2  |             46.41 |                        2.33 |
| 20x 0.5 um/step |              20.14 |              27.4  |                      202.78 |                      100.6  |           203.77 |           104.26 |             48.83 |                        2.24 |
| 20x 1 um/step   |              50.42 |              34.01 |                      176.8  |                       86.85 |           183.85 |            93.27 |             49.27 |                        2.46 |
| 5x 0.5 um/step  |               8.91 |               9.55 |                      473.47 |                      355.95 |           473.55 |           356.07 |             24.81 |                        1.46 |
| 5x 1 um/step    |              61.93 |              60.93 |                      487.35 |                      365.78 |           491.27 |           370.82 |             24.52 |                        1.44 |

## Short interpretation

- V41-Standalone lowers total displacement readout uncertainty in all 6/6 datasets.
- Mean improvement across the six datasets is 40.89%.
- Worst-case improvement is still positive at 24.52%.
- This is the cleanest way to explain why Raw can have a small step SD but still be a weaker metrology signal: its boundary position is much less certain.

## Output files

- tables/uncertainty_aware_displacement_readout.csv
- tables/uncertainty_aware_displacement_delta.csv
- figures/uncertainty_aware_displacement_total_uncertainty.png
- figures/v41_standalone_total_uncertainty_improvement_vs_raw.png