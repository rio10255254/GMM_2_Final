# Boundary-sensitive ROI V41 comparison

Method: fixed manual ROI, Sobel edge projection, one-dimensional profile matching, and subpixel parabolic refinement.
Compared cases: Raw, Old V41, and V41-Standalone. The same ROI and frame order are used inside each dataset/group.

## Main all-step comparison

| dataset | group | case | steps | std um | median error um | improvement vs Raw |
|---|---|---|---:|---:|---:|---:|
| 20260702_100MG | x_0p5um | Raw | 50 | 0.038528 | 0.005852 | +0.00% |
| 20260702_100MG | x_0p5um | Old V41 | 50 | 0.038473 | 0.004595 | +0.14% |
| 20260702_100MG | x_0p5um | V41-Standalone | 50 | 0.038473 | 0.004610 | +0.14% |
| 20260702_100MG | x_1um | Raw | 49 | 0.012895 | 0.009341 | +0.00% |
| 20260702_100MG | x_1um | Old V41 | 49 | 0.010734 | 0.008081 | +16.75% |
| 20260702_100MG | x_1um | V41-Standalone | 49 | 0.010809 | 0.008419 | +16.17% |
| 20260704_20x_5x | 20x_0p5um | Raw | 49 | 0.080227 | 0.009720 | +0.00% |
| 20260704_20x_5x | 20x_0p5um | Old V41 | 49 | 0.080392 | 0.008288 | -0.21% |
| 20260704_20x_5x | 20x_0p5um | V41-Standalone | 49 | 0.080453 | 0.009392 | -0.28% |
| 20260704_20x_5x | 20x_1um | Raw | 49 | 0.025658 | 0.008743 | +0.00% |
| 20260704_20x_5x | 20x_1um | Old V41 | 49 | 0.025113 | 0.010663 | +2.13% |
| 20260704_20x_5x | 20x_1um | V41-Standalone | 49 | 0.025298 | 0.010231 | +1.40% |
| 20260704_20x_5x | 5x_0p5um | Raw | 49 | 0.011358 | 0.042948 | +0.00% |
| 20260704_20x_5x | 5x_0p5um | Old V41 | 49 | 0.011928 | 0.041919 | -5.02% |
| 20260704_20x_5x | 5x_0p5um | V41-Standalone | 49 | 0.011648 | 0.041511 | -2.56% |
| 20260704_20x_5x | 5x_1um | Raw | 49 | 0.157256 | 0.158820 | +0.00% |
| 20260704_20x_5x | 5x_1um | Old V41 | 49 | 0.157479 | 0.158073 | -0.14% |
| 20260704_20x_5x | 5x_1um | V41-Standalone | 49 | 0.157482 | 0.157386 | -0.14% |

## Common best-30 comparison

Common best-30 uses the same 30 step indices for Raw, Old V41, and V41-Standalone inside each group.

| dataset | group | case | steps | std um | median error um | improvement vs Raw |
|---|---|---|---:|---:|---:|---:|
| 20260702_100MG | x_0p5um | Raw | 30 | 0.003898 | 0.003365 | +0.00% |
| 20260702_100MG | x_0p5um | Old V41 | 30 | 0.003365 | 0.002397 | +13.67% |
| 20260702_100MG | x_0p5um | V41-Standalone | 30 | 0.003331 | 0.002437 | +14.53% |
| 20260702_100MG | x_1um | Raw | 30 | 0.007418 | 0.006426 | +0.00% |
| 20260702_100MG | x_1um | Old V41 | 30 | 0.005346 | 0.005430 | +27.93% |
| 20260702_100MG | x_1um | V41-Standalone | 30 | 0.005352 | 0.005313 | +27.85% |
| 20260704_20x_5x | 20x_0p5um | Raw | 30 | 0.006694 | 0.004320 | +0.00% |
| 20260704_20x_5x | 20x_0p5um | Old V41 | 30 | 0.005949 | 0.004643 | +11.13% |
| 20260704_20x_5x | 20x_0p5um | V41-Standalone | 30 | 0.006358 | 0.005589 | +5.03% |
| 20260704_20x_5x | 20x_1um | Raw | 30 | 0.006539 | 0.005525 | +0.00% |
| 20260704_20x_5x | 20x_1um | Old V41 | 30 | 0.006767 | 0.007666 | -3.49% |
| 20260704_20x_5x | 20x_1um | V41-Standalone | 30 | 0.006344 | 0.007064 | +2.98% |
| 20260704_20x_5x | 5x_0p5um | Raw | 30 | 0.006490 | 0.039456 | +0.00% |
| 20260704_20x_5x | 5x_0p5um | Old V41 | 30 | 0.006795 | 0.036847 | -4.70% |
| 20260704_20x_5x | 5x_0p5um | V41-Standalone | 30 | 0.006694 | 0.036483 | -3.15% |
| 20260704_20x_5x | 5x_1um | Raw | 30 | 0.067906 | 0.090199 | +0.00% |
| 20260704_20x_5x | 5x_1um | Old V41 | 30 | 0.067731 | 0.088737 | +0.26% |
| 20260704_20x_5x | 5x_1um | V41-Standalone | 30 | 0.067695 | 0.089249 | +0.31% |

## Best V41 reading by group

| selection | dataset | group | best V41 | improvement vs Raw | both V41 better than Raw |
|---|---|---|---|---:|---|
| all_steps | 20260702_100MG | x_0p5um | V41-Standalone | +0.14% | True |
| common_best30 | 20260702_100MG | x_0p5um | V41-Standalone | +14.53% | True |
| raw_anchor_best30 | 20260702_100MG | x_0p5um | V41-Standalone | -4.93% | False |
| all_steps | 20260702_100MG | x_1um | Old V41 | +16.75% | True |
| common_best30 | 20260702_100MG | x_1um | Old V41 | +27.93% | True |
| raw_anchor_best30 | 20260702_100MG | x_1um | Old V41 | +2.17% | True |
| all_steps | 20260704_20x_5x | 20x_0p5um | Old V41 | -0.21% | False |
| common_best30 | 20260704_20x_5x | 20x_0p5um | Old V41 | +11.13% | True |
| raw_anchor_best30 | 20260704_20x_5x | 20x_0p5um | Old V41 | +11.13% | True |
| all_steps | 20260704_20x_5x | 20x_1um | Old V41 | +2.13% | True |
| common_best30 | 20260704_20x_5x | 20x_1um | V41-Standalone | +2.98% | False |
| raw_anchor_best30 | 20260704_20x_5x | 20x_1um | V41-Standalone | -6.66% | False |
| all_steps | 20260704_20x_5x | 5x_0p5um | V41-Standalone | -2.56% | False |
| common_best30 | 20260704_20x_5x | 5x_0p5um | V41-Standalone | -3.15% | False |
| raw_anchor_best30 | 20260704_20x_5x | 5x_0p5um | V41-Standalone | -4.30% | False |
| all_steps | 20260704_20x_5x | 5x_1um | Old V41 | -0.14% | False |
| common_best30 | 20260704_20x_5x | 5x_1um | V41-Standalone | +0.31% | True |
| raw_anchor_best30 | 20260704_20x_5x | 5x_1um | V41-Standalone | +0.31% | True |

## Data integrity

- Groups analyzed: 6
- Cases per group: raw, v41_old, v41_standalone
- Frame-name order is checked before calculation.
- All source image folders are recorded in the manifest.

## Output files

- tables/boundary_sensitive_all_steps.csv
- tables/boundary_sensitive_summary.csv
- tables/boundary_sensitive_comparison.csv
- tables/boundary_sensitive_selected_steps.csv
- tables/boundary_sensitive_v41_advantage_summary.csv
- figures/boundary_sensitive_steps_*.png
- figures/boundary_sensitive_std_*.png
- figures/boundary_sensitive_v41_advantage_*.png
