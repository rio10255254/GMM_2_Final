# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | v7_anchor_blend10 | -0.122 | -2.444 | 3 | -7.754 | -97.876 |
| 2 | v17_native_anchor_probe30 | 0.611 | -6.826 | 3 | -11.058 | -100.446 |
| 3 | v7_anchor_detail035 | 0.901 | -10.226 | 3 | -19.434 | -108.532 |
| 4 | v17_native_anchor_e3_mtb300 | 4.429 | -11.116 | 3 | -39.981 | -125.552 |
| 5 | v11_motionclean_latest_probe300 | -38.764 | -50.819 | 4 | -87.647 | -246.410 |
| 6 | v7_anchor_detail100 | 12.088 | -136.244 | 4 | -231.630 | -339.542 |
| 7 | v18_native_anchor_conservative_e3_mtb300 | -761.228 | 0.757 | 2 | -8.575 | -829.803 |
| 8 | v7_anchor_blend40 | -779.403 | -6.708 | 3 | -26.153 | -895.556 |
| 9 | v16_strong_lowfreq_probe_mtb80 | -797.878 | -67.729 | 4 | -112.151 | -1030.030 |
| 10 | v14_lowfreq_probe_mtb80 | -801.641 | -79.148 | 4 | -117.344 | -1038.985 |
| 11 | v8_gmfgate_smoke_mtb2 | -796.133 | -73.566 | 4 | -124.478 | -1040.611 |
| 12 | v15_main_lowfreq_probe_mtb80 | -802.659 | -74.264 | 4 | -118.306 | -1040.965 |
| 13 | r61 | -796.142 | -73.673 | 4 | -124.846 | -1040.987 |
| 14 | v2_targetboost | -796.142 | -73.674 | 4 | -124.846 | -1040.987 |
| 15 | v11_motionclean_from_v7_probe300 | -801.780 | -72.986 | 4 | -124.958 | -1046.737 |
| 16 | v7 | -801.780 | -72.986 | 4 | -124.958 | -1046.737 |
| 17 | v8_gmfgate_probe_mtb120 | -800.576 | -75.283 | 4 | -136.952 | -1057.527 |
| 18 | noamp_short_e2_b200_latest | -793.171 | -84.918 | 4 | -165.546 | -1078.717 |
| 19 | v12_motioncenter_fromv7_probe | -801.972 | -79.175 | 4 | -176.291 | -1098.263 |
| 20 | v13_localmotioncenter_fromv7_probe | -802.737 | -81.765 | 4 | -189.599 | -1112.336 |
| 21 | noamp_probe8_latest | -792.543 | -203.083 | 4 | -674.367 | -1586.910 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | noamp_short_e2_b200_latest |
| 20260702_100MG | x_1um | primary | v7_anchor_detail100 |
| 20260704_20x_5x | 20x_0p5um | guardrail | v17_native_anchor_e3_mtb300 |
| 20260704_20x_5x | 20x_1um | guardrail | raw |
| 20260704_20x_5x | 5x_0p5um | guardrail | v18_native_anchor_conservative_e3_mtb300 |
| 20260704_20x_5x | 5x_1um | guardrail | v7_anchor_blend40 |
