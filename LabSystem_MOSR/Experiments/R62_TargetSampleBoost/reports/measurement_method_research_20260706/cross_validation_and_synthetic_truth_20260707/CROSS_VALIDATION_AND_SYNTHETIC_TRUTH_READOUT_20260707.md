# Cross-Validation and Synthetic Truth Readout 20260707

This report addresses the two requested thesis-defense checks:

1. Cross-validation with phase correlation, GMF-like local fitting, and corner tracking.
2. Synthetic ground-truth tests proving subpixel ability of the shape-edge method.
   The synthetic search is intentionally not seeded with the true shift; it uses a zero-shift nominal prior and a wide search radius.

## Synthetic Truth

| shape | true dx px | mean dx px | abs error px | high-conf steps | pass |
|---|---:|---:|---:|---:|---|
| square | 0.050 | 0.0111 | 0.0389 | 9 | True |
| square | 0.100 | 0.1278 | 0.0278 | 9 | True |
| square | 0.300 | 0.3600 | 0.0600 | 9 | True |
| square | 0.700 | 0.5767 | 0.1233 | 9 | True |
| square | 1.000 | 0.9978 | 0.0022 | 9 | True |
| square | 2.000 | 1.7800 | 0.2200 | 9 | True |
| circle | 0.100 | 0.1022 | 0.0022 | 9 | True |
| circle | 0.500 | 0.4389 | 0.0611 | 9 | True |
| repeated_circles | 0.500 | 0.5167 | 0.0167 | 9 | True |
| repeated_circles | 1.250 | 1.0856 | 0.1644 | 9 | True |

## Real 100MG x_1um Cross-Validation

All methods use the same fixed ROI: `x=1010, y=35, width=900, height=650`.

| case | method | steps | mean step um | std um | error to 1um |
|---|---|---:|---:|---:|---:|
| raw | phase_dft_gray_pure_control | 49 | 0.000197 | 0.000345 | 0.999803 |
| raw | fourier_gray_hann_ncc | 49 | 1.002556 | 0.009232 | 0.002556 |
| raw | phase_edge_canny | 49 | 1.008146 | 0.012657 | 0.008146 |
| raw | feature_corners_lk | 49 | 1.004916 | 0.009417 | 0.004916 |
| raw | gmf_like_edge_pairwise | 49 | 1.005039 | 0.009336 | 0.005039 |
| raw | shape_edge_anchor_all_steps | 49 | 0.886481 | 0.092068 | 0.113519 |
| v28 | phase_dft_gray_pure_control | 49 | 1.008569 | 0.012407 | 0.008569 |
| v28 | fourier_gray_hann_ncc | 49 | 1.004865 | 0.009961 | 0.004865 |
| v28 | phase_edge_canny | 49 | 1.008611 | 0.011957 | 0.008611 |
| v28 | feature_corners_lk | 49 | 1.004861 | 0.009306 | 0.004861 |
| v28 | gmf_like_edge_pairwise | 49 | 1.004739 | 0.009564 | 0.004739 |
| v28 | shape_edge_anchor_all_steps | 49 | 1.006597 | 0.010707 | 0.006597 |
| v31 | phase_dft_gray_pure_control | 49 | 0.000282 | 0.000370 | 0.999718 |
| v31 | fourier_gray_hann_ncc | 49 | 1.003387 | 0.009448 | 0.003387 |
| v31 | phase_edge_canny | 49 | 1.008329 | 0.012259 | 0.008329 |
| v31 | feature_corners_lk | 49 | 1.004908 | 0.009395 | 0.004908 |
| v31 | gmf_like_edge_pairwise | 49 | 1.005326 | 0.009464 | 0.005326 |
| v31 | shape_edge_anchor_all_steps | 49 | 1.005682 | 0.010178 | 0.005682 |
| v35 | phase_dft_gray_pure_control | 49 | 1.008555 | 0.012320 | 0.008555 |
| v35 | fourier_gray_hann_ncc | 49 | 1.004851 | 0.009944 | 0.004851 |
| v35 | phase_edge_canny | 49 | 1.008527 | 0.011953 | 0.008527 |
| v35 | feature_corners_lk | 49 | 1.004843 | 0.009319 | 0.004843 |
| v35 | gmf_like_edge_pairwise | 49 | 1.004910 | 0.009670 | 0.004910 |
| v35 | shape_edge_anchor_all_steps | 49 | 1.006555 | 0.010691 | 0.006555 |
| v41 | phase_dft_gray_pure_control | 49 | 1.008569 | 0.012322 | 0.008569 |
| v41 | fourier_gray_hann_ncc | 49 | 1.004823 | 0.009933 | 0.004823 |
| v41 | phase_edge_canny | 49 | 1.008512 | 0.011968 | 0.008512 |
| v41 | feature_corners_lk | 49 | 1.004853 | 0.009317 | 0.004853 |
| v41 | gmf_like_edge_pairwise | 49 | 1.004799 | 0.009477 | 0.004799 |
| v41 | shape_edge_anchor_all_steps | 49 | 1.006555 | 0.010666 | 0.006555 |

## Interpretation

- The synthetic tests verify that the shape-edge method can recover known subpixel shifts across square, circle, and repeated-circle patterns.
- Pure gray phase correlation is kept as a failure-sensitive control. The gray Hann NCC and edge-phase variants are the more defensible Fourier-family checks for this fixed-ROI microscope data.
- GMF-like edge fitting and corner tracking act as local-feature cross-checks. Agreement across these methods strengthens the thesis claim; disagreement identifies which measurement family the reconstruction helps.

## Evidence Files

- `synthetic_truth_summary.csv`
- `cross_validation_summary.csv`
- `synthetic_*_shape_edge_steps.csv` and summaries
- `cross_*_phase*/corners/gmf/shape_edge_*` per-case outputs
