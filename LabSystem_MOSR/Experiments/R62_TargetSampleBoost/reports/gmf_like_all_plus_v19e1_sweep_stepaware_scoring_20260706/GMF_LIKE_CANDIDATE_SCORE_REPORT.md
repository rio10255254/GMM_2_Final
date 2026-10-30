# GMF-like candidate score report

This report merges GMF-like displacement readouts and ranks candidate reconstructions against Raw.

## Candidate Ranking

| rank | case | primary mean % | guardrail mean % | guardrail worse | worst guardrail % | step err penalty | score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | v7_anchor_blend10 | -0.122 | -2.444 | 3 | -7.754 | 4.050 | -101.926 |
| 2 | v19e1m200 | 4.101 | -5.059 | 2 | -42.577 | 3.761 | -102.237 |
| 3 | v17_native_anchor_probe30 | 0.611 | -6.826 | 3 | -11.058 | 4.138 | -104.585 |
| 4 | v7_anchor_detail035 | 0.901 | -10.226 | 3 | -19.434 | 4.234 | -112.766 |
| 5 | v19e1m300 | 4.365 | -10.221 | 3 | -39.842 | 3.693 | -129.170 |
| 6 | v19e1m120 | 4.566 | -8.842 | 3 | -40.921 | 3.705 | -130.060 |
| 7 | v17_native_anchor_e3_mtb300 | 4.429 | -11.116 | 3 | -39.981 | 4.661 | -130.213 |
| 8 | v17e3 | 4.429 | -11.116 | 3 | -39.981 | 4.661 | -130.213 |
| 9 | v11_motionclean_latest_probe300 | -38.764 | -50.819 | 4 | -87.647 | 6.304 | -252.715 |
| 10 | v7_anchor_detail100 | 12.088 | -136.244 | 4 | -231.630 | 9.040 | -348.582 |
| 11 | v18_native_anchor_conservative_e3_mtb300 | -761.228 | 0.757 | 2 | -8.575 | 8.387 | -838.190 |
| 12 | v7_anchor_blend40 | -779.403 | -6.708 | 3 | -26.153 | 9.314 | -904.870 |
| 13 | v16_strong_lowfreq_probe_mtb80 | -797.878 | -67.729 | 4 | -112.151 | 12.432 | -1042.461 |
| 14 | v14_lowfreq_probe_mtb80 | -801.641 | -79.148 | 4 | -117.344 | 8.102 | -1047.087 |
| 15 | v15_main_lowfreq_probe_mtb80 | -802.659 | -74.264 | 4 | -118.306 | 10.126 | -1051.091 |
| 16 | v8_gmfgate_smoke_mtb2 | -796.133 | -73.566 | 4 | -124.478 | 12.440 | -1053.050 |
| 17 | r61 | -796.142 | -73.673 | 4 | -124.846 | 12.434 | -1053.422 |
| 18 | v2_targetboost | -796.142 | -73.674 | 4 | -124.846 | 12.434 | -1053.422 |
| 19 | v11_motionclean_from_v7_probe300 | -801.780 | -72.986 | 4 | -124.958 | 12.318 | -1059.056 |
| 20 | v7 | -801.780 | -72.986 | 4 | -124.958 | 12.318 | -1059.056 |
| 21 | v8_gmfgate_probe_mtb120 | -800.576 | -75.283 | 4 | -136.952 | 12.526 | -1070.053 |
| 22 | noamp_short_e2_b200_latest | -793.171 | -84.918 | 4 | -165.546 | 12.797 | -1091.514 |
| 23 | v12_motioncenter_fromv7_probe | -801.972 | -79.175 | 4 | -176.291 | 12.360 | -1110.624 |
| 24 | v13_localmotioncenter_fromv7_probe | -802.737 | -81.765 | 4 | -189.599 | 12.368 | -1124.704 |
| 25 | noamp_probe8_latest | -792.543 | -203.083 | 4 | -674.367 | 19.447 | -1606.357 |

## Group Winners

| dataset | group | tier | best case |
|---|---|---|---|
| 20260702_100MG | x_0p5um | primary | noamp_short_e2_b200_latest |
| 20260702_100MG | x_1um | primary | v7_anchor_detail100 |
| 20260704_20x_5x | 20x_0p5um | guardrail | v19e1m300 |
| 20260704_20x_5x | 20x_1um | guardrail | raw |
| 20260704_20x_5x | 5x_0p5um | guardrail | v18_native_anchor_conservative_e3_mtb300 |
| 20260704_20x_5x | 5x_1um | guardrail | v7_anchor_blend40 |
