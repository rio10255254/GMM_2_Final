# 100MG Center 6x6 Individual CD Validation

Every row is a fixed physical pillar or via, mapped to its SEM cell. No per-model coordinate recalibration was used.

## Summary

| feature_key   | feature_label   | case           | case_label     |   n_features |   mean_abs_error_nm |   median_abs_error_nm |   max_abs_error_nm |   within_50nm_count |   within_100nm_count |   best_feature_count |   mean_improvement_vs_raw_nm |   median_improvement_vs_raw_nm |
|:--------------|:----------------|:---------------|:---------------|-------------:|--------------------:|----------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-----------------------------:|-------------------------------:|
| pillar        | Pillar          | raw            | Raw            |           36 |               81.26 |                 72.17 |             148.48 |                   8 |                   24 |                    0 |                         0.00 |                           0.00 |
| pillar        | Pillar          | v41_standalone | V41 standalone |           36 |               64.60 |                 58.83 |             140.72 |                  15 |                   28 |                   22 |                        16.66 |                          13.34 |
| pillar        | Pillar          | v42_e010       | V42 epoch 10   |           36 |               66.15 |                 60.46 |             132.47 |                  13 |                   27 |                    6 |                        15.11 |                          11.71 |
| pillar        | Pillar          | v42_e023       | V42 epoch 23   |           36 |               70.80 |                 65.19 |             136.61 |                  10 |                   26 |                    0 |                        10.46 |                           6.98 |
| pillar        | Pillar          | v42_e094       | V42 epoch 94   |           36 |               66.40 |                 60.94 |             133.14 |                  12 |                   27 |                    8 |                        14.85 |                          11.23 |
| via           | Via             | raw            | Raw            |           36 |              314.11 |                225.18 |            1344.94 |                   0 |                    0 |                    1 |                         0.00 |                           0.00 |
| via           | Via             | v41_standalone | V41 standalone |           36 |              243.14 |                145.62 |            1431.40 |                   0 |                    1 |                   35 |                        70.97 |                          79.56 |
| via           | Via             | v42_e010       | V42 epoch 10   |           36 |              256.18 |                158.18 |            1432.70 |                   0 |                    0 |                    0 |                        57.93 |                          67.00 |
| via           | Via             | v42_e023       | V42 epoch 23   |           36 |              265.66 |                168.54 |            1430.05 |                   0 |                    0 |                    0 |                        48.45 |                          56.64 |
| via           | Via             | v42_e094       | V42 epoch 94   |           36 |              261.83 |                163.47 |            1397.55 |                   0 |                    0 |                    0 |                        52.28 |                          61.71 |

## Interpretation rule

Positive `mean_improvement_vs_raw_nm` means the case has a smaller mean absolute CD error than Raw. The individual wide table must be used to see whether an average hides any worse locations.