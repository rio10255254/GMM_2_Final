# Old R26 vs New Retrain Delta Matrix

這張表只列出非 PSF 本體之外，舊 R26 run 與新 retrain run 已確認不同的執行/選模條件。

| field | old | new |
| --- | --- | --- |
| model_name | GESR_v1_v5_ST0p8_SWP_r26sm035 | GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest |
| run_tag | GESR_v1_v5_ST0p8_SWP_r26sm035_20260316_190408 | GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223 |
| amp | False | True |
| seed_deterministic | True | False |
| cudnn_deterministic | True | False |
| cudnn_benchmark | False | True |
| tf32_matmul | False | True |
| tf32_cudnn | False | True |
| val_epoch_count | 12 | 100 |
| val_epoch_last | 12 | 100 |
| best_tradeoff_epoch | 1 | 16 |
| proxy_nonzero_epochs | 0 | 50 |
| gmf_nonzero_epochs | 0 | 49 |
| expected_enable | 1 | 0 |
| expected_step_px | 0.8 | 0.0 |
| expect_dx_px | 0.0 | None |
| expect_dy_px | 0.8 | None |

重點：這代表目前壞結果不能被簡化成「只換 PSF」。