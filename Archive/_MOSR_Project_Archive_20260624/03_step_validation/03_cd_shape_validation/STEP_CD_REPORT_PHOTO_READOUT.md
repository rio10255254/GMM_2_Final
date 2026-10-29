# Step sample CD check from calibration-report photo

Scale used: camera pixel 2.5 um / 20x objective = 0.125 um/px.

Important interpretation: the provided Mitutoyo photo is a circle form-deviation / roundness page. It confirms nominal circle sizes such as phi 0.3 mm and phi 0.1 mm, but it is not a direct diameter calibration table. I therefore compare image measurements to nominal diameters, not to a certified CD value from that page.

Report photo values readable for the relevant rows: phi 0.3 mm roundness is about 0.000057 mm (0.057 um), and phi 0.1 mm roundness is about 0.000059 mm (0.059 um). These are shape-deviation magnitudes, not optical-image CD errors.

## Summary
- full_original_raw target 100 um: measured 99.320 um, error -0.680 um, threshold sensitivity +/-0.331 um.
- full_original_raw target 200 um: measured 199.546 um, error -0.454 um, threshold sensitivity +/-0.342 um.
- full_original_raw target 300 um: measured 299.733 um, error -0.267 um, threshold sensitivity +/-0.343 um.
- full_original_raw target 500 um: measured 499.894 um, error -0.106 um, threshold sensitivity +/-0.352 um.
- center2048_raw_1um_rep0 target 100 um: measured 99.283 um, error -0.717 um, threshold sensitivity +/-0.332 um.
- center2048_raw_1um_rep0 target 200 um: measured 199.512 um, error -0.488 um, threshold sensitivity +/-0.340 um.
- center2048_v16_1um_rep0 target 100 um: measured 99.458 um, error -0.542 um, threshold sensitivity +/-0.026 um.
- center2048_v16_1um_rep0 target 200 um: measured 199.691 um, error -0.309 um, threshold sensitivity +/-0.027 um.

Files:
- CSV: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/step_cd_measurement_summary.csv
- Full raw overlay: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/full_original_raw_cd_overlay.png
- Center v16 overlay: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/center2048_v16_1um_rep0_cd_overlay.png
## Center2048 all 1um rep0 frames

- center2048_r39_1um_rep0 target 100 um: mean 99.463 um, std 0.0031 um, mean error -0.537 um, n=40.
- center2048_r39_1um_rep0 target 200 um: mean 199.694 um, std 0.0024 um, mean error -0.306 um, n=40.
- center2048_raw_1um_rep0 target 100 um: mean 99.288 um, std 0.0035 um, mean error -0.712 um, n=40.
- center2048_raw_1um_rep0 target 200 um: mean 199.519 um, std 0.0038 um, mean error -0.481 um, n=40.
- center2048_v14_1um_rep0 target 100 um: mean 99.463 um, std 0.0030 um, mean error -0.537 um, n=40.
- center2048_v14_1um_rep0 target 200 um: mean 199.694 um, std 0.0026 um, mean error -0.306 um, n=40.
- center2048_v16_1um_rep0 target 100 um: mean 99.462 um, std 0.0032 um, mean error -0.538 um, n=40.
- center2048_v16_1um_rep0 target 200 um: mean 199.692 um, std 0.0028 um, mean error -0.308 um, n=40.

Center all-frame CSV: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/step_cd_center2048_all_1um_rep0_frames.csv
Center all-frame summary CSV: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/step_cd_center2048_all_1um_rep0_summary.csv

## Full raw matching 1um package names

- full raw target 100 um: mean 99.321 um, std 0.0034 um, mean error -0.679 um, n=40.
- full raw target 200 um: mean 199.553 um, std 0.0036 um, mean error -0.447 um, n=40.
- full raw target 300 um: mean 299.736 um, std 0.0037 um, mean error -0.264 um, n=40.
- full raw target 500 um: mean 499.905 um, std 0.0041 um, mean error -0.095 um, n=40.

Full raw CSV: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/step_cd_full_raw_matching_1um_names.csv
Full raw summary CSV: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/step_cd_full_raw_matching_1um_names_summary.csv

## All 1um rep0 frames summary

- center2048_r39_1um_rep0 target 100 um: mean 99.463 um, frame-to-frame std 0.003 um, mean error -0.537 um, n=40.
- center2048_r39_1um_rep0 target 200 um: mean 199.694 um, frame-to-frame std 0.002 um, mean error -0.306 um, n=40.
- center2048_raw_1um_rep0 target 100 um: mean 99.288 um, frame-to-frame std 0.003 um, mean error -0.712 um, n=40.
- center2048_raw_1um_rep0 target 200 um: mean 199.519 um, frame-to-frame std 0.004 um, mean error -0.481 um, n=40.
- center2048_v14_1um_rep0 target 100 um: mean 99.463 um, frame-to-frame std 0.003 um, mean error -0.537 um, n=40.
- center2048_v14_1um_rep0 target 200 um: mean 199.694 um, frame-to-frame std 0.003 um, mean error -0.306 um, n=40.
- center2048_v16_1um_rep0 target 100 um: mean 99.462 um, frame-to-frame std 0.003 um, mean error -0.538 um, n=40.
- center2048_v16_1um_rep0 target 200 um: mean 199.692 um, frame-to-frame std 0.003 um, mean error -0.308 um, n=40.
- full_original_raw_matching_1um_names target 100 um: mean 99.321 um, frame-to-frame std 0.003 um, mean error -0.679 um, n=40.
- full_original_raw_matching_1um_names target 200 um: mean 199.553 um, frame-to-frame std 0.004 um, mean error -0.447 um, n=40.
- full_original_raw_matching_1um_names target 300 um: mean 299.736 um, frame-to-frame std 0.004 um, mean error -0.264 um, n=40.
- full_original_raw_matching_1um_names target 500 um: mean 499.905 um, frame-to-frame std 0.004 um, mean error -0.095 um, n=40.

All-frame CSV: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/step_cd_measurement_all_1um_rep0_frames.csv
All-frame summary CSV: Analyses/Step_analysis_20260623/step_cd_report_photo_check_20260624/step_cd_measurement_all_1um_rep0_summary.csv
