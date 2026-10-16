# GMF-like thesis displacement gate

This gate uses fixed ROIs and the open GMF-like local fitting tool.
It is intended for model selection on thesis displacement behavior, not for training loss by itself.

## Case Results

| dataset | group | case | std um | step um | status |
|---|---|---|---:|---:|---|
| 20260702_100MG | x_1um | raw | 0.024995 | 0.999814 | ok |
| 20260702_100MG | x_1um | r61 | 0.422301 | 0.903308 | ok |
| 20260702_100MG | x_1um | v7 | 0.423655 | 0.903724 | ok |
| 20260702_100MG | x_1um | noamp_probe8_latest | 0.421215 | 0.902639 | ok |
| 20260702_100MG | x_1um | noamp_short_e2_b200_latest | 0.422615 | 0.901053 | ok |
| 20260702_100MG | x_1um | v11_motionclean_from_v7_probe300 | 0.423655 | 0.903724 | ok |
| 20260702_100MG | x_1um | v11_motionclean_latest_probe300 | 0.042711 | 0.999172 | ok |
| 20260702_100MG | x_1um | v12_motioncenter_fromv7_probe | 0.423660 | 0.900635 | ok |
| 20260702_100MG | x_1um | v13_localmotioncenter_fromv7_probe | 0.423934 | 0.900267 | ok |
| 20260702_100MG | x_1um | v14_lowfreq_probe_mtb80 | 0.423866 | 0.903547 | ok |
| 20260702_100MG | x_1um | v15_main_lowfreq_probe_mtb80 | 0.424177 | 0.903093 | ok |
| 20260702_100MG | x_1um | v16_strong_lowfreq_probe_mtb80 | 0.422684 | 0.903182 | ok |
| 20260702_100MG | x_1um | v17_native_anchor_e3_mtb300 | 0.022930 | 0.999750 | ok |
| 20260702_100MG | x_1um | v17_native_anchor_probe30 | 0.024745 | 1.001648 | ok |
| 20260702_100MG | x_1um | v18_native_anchor_conservative_e3_mtb300 | 0.405636 | 0.907596 | ok |
| 20260702_100MG | x_1um | v2_targetboost | 0.422301 | 0.903308 | ok |
| 20260702_100MG | x_1um | v7_anchor_blend10 | 0.025372 | 1.000892 | ok |
| 20260702_100MG | x_1um | v7_anchor_blend40 | 0.415677 | 0.904730 | ok |
| 20260702_100MG | x_1um | v7_anchor_detail035 | 0.024592 | 1.001798 | ok |
| 20260702_100MG | x_1um | v7_anchor_detail100 | 0.018049 | 0.992864 | ok |
| 20260702_100MG | x_1um | v8_gmfgate_probe_mtb120 | 0.423042 | 0.903469 | ok |
| 20260702_100MG | x_1um | v8_gmfgate_smoke_mtb2 | 0.422298 | 0.903308 | ok |
| 20260702_100MG | x_0p5um | raw | 0.042373 | 0.511274 | ok |
| 20260702_100MG | x_0p5um | r61 | 0.043543 | 0.509620 | ok |
| 20260702_100MG | x_0p5um | v7 | 0.046027 | 0.508243 | ok |
| 20260702_100MG | x_0p5um | noamp_probe8_latest | 0.042335 | 0.509164 | ok |
| 20260702_100MG | x_0p5um | noamp_short_e2_b200_latest | 0.040494 | 0.507376 | ok |
| 20260702_100MG | x_0p5um | v11_motionclean_from_v7_probe300 | 0.046027 | 0.508243 | ok |
| 20260702_100MG | x_0p5um | v11_motionclean_latest_probe300 | 0.045192 | 0.506361 | ok |
| 20260702_100MG | x_0p5um | v12_motioncenter_fromv7_probe | 0.046181 | 0.508318 | ok |
| 20260702_100MG | x_0p5um | v13_localmotioncenter_fromv7_probe | 0.046364 | 0.508428 | ok |
| 20260702_100MG | x_0p5um | v14_lowfreq_probe_mtb80 | 0.045551 | 0.509310 | ok |
| 20260702_100MG | x_0p5um | v15_main_lowfreq_probe_mtb80 | 0.045886 | 0.508161 | ok |
| 20260702_100MG | x_0p5um | v16_strong_lowfreq_probe_mtb80 | 0.044366 | 0.508921 | ok |
| 20260702_100MG | x_0p5um | v17_native_anchor_e3_mtb300 | 0.042122 | 0.511567 | ok |
| 20260702_100MG | x_0p5um | v17_native_anchor_probe30 | 0.042280 | 0.511487 | ok |
| 20260702_100MG | x_0p5um | v18_native_anchor_conservative_e3_mtb300 | 0.042206 | 0.511544 | ok |
| 20260702_100MG | x_0p5um | v2_targetboost | 0.043543 | 0.509620 | ok |
| 20260702_100MG | x_0p5um | v7_anchor_blend10 | 0.041838 | 0.511371 | ok |
| 20260702_100MG | x_0p5um | v7_anchor_blend40 | 0.040587 | 0.510839 | ok |
| 20260702_100MG | x_0p5um | v7_anchor_detail035 | 0.042294 | 0.511465 | ok |
| 20260702_100MG | x_0p5um | v7_anchor_detail100 | 0.043906 | 0.511616 | ok |
| 20260702_100MG | x_0p5um | v8_gmfgate_probe_mtb120 | 0.046045 | 0.508650 | ok |
| 20260702_100MG | x_0p5um | v8_gmfgate_smoke_mtb2 | 0.043541 | 0.509611 | ok |
| 20260704_20x_5x | 20x_1um | raw | 0.035031 | 1.003353 | ok |
| 20260704_20x_5x | 20x_1um | r61 | 0.045421 | 0.998299 | ok |
| 20260704_20x_5x | 20x_1um | v7 | 0.046646 | 0.998083 | ok |
| 20260704_20x_5x | 20x_1um | noamp_probe8_latest | 0.045994 | 0.998638 | ok |
| 20260704_20x_5x | 20x_1um | noamp_short_e2_b200_latest | 0.048613 | 0.998940 | ok |
| 20260704_20x_5x | 20x_1um | v11_motionclean_from_v7_probe300 | 0.046646 | 0.998083 | ok |
| 20260704_20x_5x | 20x_1um | v11_motionclean_latest_probe300 | 0.054531 | 0.998528 | ok |
| 20260704_20x_5x | 20x_1um | v12_motioncenter_fromv7_probe | 0.049567 | 0.999138 | ok |
| 20260704_20x_5x | 20x_1um | v13_localmotioncenter_fromv7_probe | 0.049711 | 0.999035 | ok |
| 20260704_20x_5x | 20x_1um | v14_lowfreq_probe_mtb80 | 0.046505 | 0.997797 | ok |
| 20260704_20x_5x | 20x_1um | v15_main_lowfreq_probe_mtb80 | 0.046224 | 0.997722 | ok |
| 20260704_20x_5x | 20x_1um | v16_strong_lowfreq_probe_mtb80 | 0.046344 | 0.997891 | ok |
| 20260704_20x_5x | 20x_1um | v17_native_anchor_e3_mtb300 | 0.049037 | 0.998695 | ok |
| 20260704_20x_5x | 20x_1um | v17_native_anchor_probe30 | 0.038368 | 1.002085 | ok |
| 20260704_20x_5x | 20x_1um | v18_native_anchor_conservative_e3_mtb300 | 0.037692 | 1.004225 | ok |
| 20260704_20x_5x | 20x_1um | v2_targetboost | 0.045421 | 0.998299 | ok |
| 20260704_20x_5x | 20x_1um | v7_anchor_blend10 | 0.036254 | 1.004078 | ok |
| 20260704_20x_5x | 20x_1um | v7_anchor_blend40 | 0.036577 | 1.005743 | ok |
| 20260704_20x_5x | 20x_1um | v7_anchor_detail035 | 0.038577 | 1.003329 | ok |
| 20260704_20x_5x | 20x_1um | v7_anchor_detail100 | 0.063749 | 0.998981 | ok |
| 20260704_20x_5x | 20x_1um | v8_gmfgate_probe_mtb120 | 0.046513 | 0.997968 | ok |
| 20260704_20x_5x | 20x_1um | v8_gmfgate_smoke_mtb2 | 0.045423 | 0.998289 | ok |
| 20260704_20x_5x | 20x_0p5um | raw | 0.080497 | 0.491105 | ok |
| 20260704_20x_5x | 20x_0p5um | r61 | 0.175064 | 0.494751 | ok |
| 20260704_20x_5x | 20x_0p5um | v7 | 0.170723 | 0.496367 | ok |
| 20260704_20x_5x | 20x_0p5um | noamp_probe8_latest | 0.623345 | 0.085131 | ok |
| 20260704_20x_5x | 20x_0p5um | noamp_short_e2_b200_latest | 0.173122 | 0.496722 | ok |
| 20260704_20x_5x | 20x_0p5um | v11_motionclean_from_v7_probe300 | 0.170723 | 0.496367 | ok |
| 20260704_20x_5x | 20x_0p5um | v11_motionclean_latest_probe300 | 0.120522 | 0.496346 | ok |
| 20260704_20x_5x | 20x_0p5um | v12_motioncenter_fromv7_probe | 0.222407 | 0.439019 | ok |
| 20260704_20x_5x | 20x_0p5um | v13_localmotioncenter_fromv7_probe | 0.233120 | 0.437904 | ok |
| 20260704_20x_5x | 20x_0p5um | v14_lowfreq_probe_mtb80 | 0.174957 | 0.499016 | ok |
| 20260704_20x_5x | 20x_0p5um | v15_main_lowfreq_probe_mtb80 | 0.175731 | 0.497800 | ok |
| 20260704_20x_5x | 20x_0p5um | v16_strong_lowfreq_probe_mtb80 | 0.165500 | 0.497453 | ok |
| 20260704_20x_5x | 20x_0p5um | v17_native_anchor_e3_mtb300 | 0.061239 | 0.485821 | ok |
| 20260704_20x_5x | 20x_0p5um | v17_native_anchor_probe30 | 0.078665 | 0.488945 | ok |
| 20260704_20x_5x | 20x_0p5um | v18_native_anchor_conservative_e3_mtb300 | 0.076202 | 0.488905 | ok |
| 20260704_20x_5x | 20x_0p5um | v2_targetboost | 0.175064 | 0.494751 | ok |
| 20260704_20x_5x | 20x_0p5um | v7_anchor_blend10 | 0.080778 | 0.491065 | ok |
| 20260704_20x_5x | 20x_0p5um | v7_anchor_blend40 | 0.081481 | 0.489074 | ok |
| 20260704_20x_5x | 20x_0p5um | v7_anchor_detail035 | 0.078744 | 0.489282 | ok |
| 20260704_20x_5x | 20x_0p5um | v7_anchor_detail100 | 0.266954 | 0.387500 | ok |
| 20260704_20x_5x | 20x_0p5um | v8_gmfgate_probe_mtb120 | 0.168539 | 0.495671 | ok |
| 20260704_20x_5x | 20x_0p5um | v8_gmfgate_smoke_mtb2 | 0.175050 | 0.494750 | ok |
| 20260704_20x_5x | 5x_1um | raw | 0.322779 | 0.795890 | ok |
| 20260704_20x_5x | 5x_1um | r61 | 0.396083 | 0.456660 | ok |
| 20260704_20x_5x | 5x_1um | v7 | 0.392967 | 0.455888 | ok |
| 20260704_20x_5x | 5x_1um | noamp_probe8_latest | 0.413384 | 0.313790 | ok |
| 20260704_20x_5x | 5x_1um | noamp_short_e2_b200_latest | 0.388274 | 0.406484 | ok |
| 20260704_20x_5x | 5x_1um | v11_motionclean_from_v7_probe300 | 0.392967 | 0.455888 | ok |
| 20260704_20x_5x | 5x_1um | v11_motionclean_latest_probe300 | 0.355847 | 0.572699 | ok |
| 20260704_20x_5x | 5x_1um | v12_motioncenter_fromv7_probe | 0.431548 | 0.535006 | ok |
| 20260704_20x_5x | 5x_1um | v13_localmotioncenter_fromv7_probe | 0.434962 | 0.539325 | ok |
| 20260704_20x_5x | 5x_1um | v14_lowfreq_probe_mtb80 | 0.579512 | 0.806262 | ok |
| 20260704_20x_5x | 5x_1um | v15_main_lowfreq_probe_mtb80 | 0.464279 | 0.634036 | ok |
| 20260704_20x_5x | 5x_1um | v16_strong_lowfreq_probe_mtb80 | 0.390153 | 0.451923 | ok |
| 20260704_20x_5x | 5x_1um | v17_native_anchor_e3_mtb300 | 0.353411 | 0.728774 | ok |
| 20260704_20x_5x | 5x_1um | v17_native_anchor_probe30 | 0.358471 | 0.786500 | ok |
| 20260704_20x_5x | 5x_1um | v18_native_anchor_conservative_e3_mtb300 | 0.350457 | 0.804357 | ok |
| 20260704_20x_5x | 5x_1um | v2_targetboost | 0.396090 | 0.456660 | ok |
| 20260704_20x_5x | 5x_1um | v7_anchor_blend10 | 0.316911 | 0.789643 | ok |
| 20260704_20x_5x | 5x_1um | v7_anchor_blend40 | 0.306790 | 0.746994 | ok |
| 20260704_20x_5x | 5x_1um | v7_anchor_detail035 | 0.385507 | 0.779177 | ok |
| 20260704_20x_5x | 5x_1um | v7_anchor_detail100 | 0.454874 | 0.467205 | ok |
| 20260704_20x_5x | 5x_1um | v8_gmfgate_probe_mtb120 | 0.393897 | 0.450442 | ok |
| 20260704_20x_5x | 5x_1um | v8_gmfgate_smoke_mtb2 | 0.395919 | 0.456623 | ok |
| 20260704_20x_5x | 5x_0p5um | raw | 0.047274 | 0.551840 | ok |
| 20260704_20x_5x | 5x_0p5um | r61 | 0.106294 | 0.519209 | ok |
| 20260704_20x_5x | 5x_0p5um | v7 | 0.106347 | 0.517715 | ok |
| 20260704_20x_5x | 5x_0p5um | noamp_probe8_latest | 0.084432 | 0.527228 | ok |
| 20260704_20x_5x | 5x_0p5um | noamp_short_e2_b200_latest | 0.125535 | 0.500643 | ok |
| 20260704_20x_5x | 5x_0p5um | v11_motionclean_from_v7_probe300 | 0.106347 | 0.517715 | ok |
| 20260704_20x_5x | 5x_0p5um | v11_motionclean_latest_probe300 | 0.088708 | 0.543166 | ok |
| 20260704_20x_5x | 5x_0p5um | v12_motioncenter_fromv7_probe | 0.078104 | 0.531249 | ok |
| 20260704_20x_5x | 5x_0p5um | v13_localmotioncenter_fromv7_probe | 0.076018 | 0.533061 | ok |
| 20260704_20x_5x | 5x_0p5um | v14_lowfreq_probe_mtb80 | 0.088382 | 0.528188 | ok |
| 20260704_20x_5x | 5x_0p5um | v15_main_lowfreq_probe_mtb80 | 0.095949 | 0.519358 | ok |
| 20260704_20x_5x | 5x_0p5um | v16_strong_lowfreq_probe_mtb80 | 0.100293 | 0.518851 | ok |
| 20260704_20x_5x | 5x_0p5um | v17_native_anchor_e3_mtb300 | 0.056216 | 0.538915 | ok |
| 20260704_20x_5x | 5x_0p5um | v17_native_anchor_probe30 | 0.051527 | 0.551882 | ok |
| 20260704_20x_5x | 5x_0p5um | v18_native_anchor_conservative_e3_mtb300 | 0.040720 | 0.544190 | ok |
| 20260704_20x_5x | 5x_0p5um | v2_targetboost | 0.106294 | 0.519209 | ok |
| 20260704_20x_5x | 5x_0p5um | v7_anchor_blend10 | 0.050940 | 0.551588 | ok |
| 20260704_20x_5x | 5x_0p5um | v7_anchor_blend40 | 0.059637 | 0.551027 | ok |
| 20260704_20x_5x | 5x_0p5um | v7_anchor_detail035 | 0.053670 | 0.550809 | ok |
| 20260704_20x_5x | 5x_0p5um | v7_anchor_detail100 | 0.137305 | 0.501858 | ok |
| 20260704_20x_5x | 5x_0p5um | v8_gmfgate_probe_mtb120 | 0.112017 | 0.525432 | ok |
| 20260704_20x_5x | 5x_0p5um | v8_gmfgate_smoke_mtb2 | 0.106120 | 0.519620 | ok |

## Raw vs Candidate

| dataset | group | best | candidate improvement vs Raw |
|---|---|---|---:|
| 20260702_100MG | x_0p5um | noamp_short_e2_b200_latest | 0.59% |
| 20260702_100MG | x_1um | v7_anchor_detail100 | 8.26% |
| 20260704_20x_5x | 20x_0p5um | v17_native_anchor_e3_mtb300 | 23.92% |
| 20260704_20x_5x | 20x_1um | raw | -39.98% |
| 20260704_20x_5x | 5x_0p5um | v18_native_anchor_conservative_e3_mtb300 | -18.92% |
| 20260704_20x_5x | 5x_1um | v7_anchor_blend40 | -9.49% |
