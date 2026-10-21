# Common stable ROI search

## Final conclusion: No ROI satisfied the complete common-stability requirement across all magnifications and both step sizes.

The ROI was searched on the shared common-best-30 steps. One fixed ROI was required for both 0.5 and 1 um sequences at each magnification. The locked ROI was then checked on steps that were not used in the search and on the complete sequence.

- Candidate rectangles searched: 109
- Held-out groups where V42 SD is lower than Raw: 4/6
- Full-sequence groups where V42 SD is lower than Raw: 5/6
- This is an internal ROI search, not an external independent validation.

## Final ROI status

| family   | candidate_id                | status        | search_common30_pass   | four_fold_pass   | heldout_both_improve   |   heldout_min_valid | all_steps_both_improve   |   minimum_heldout_improvement_pct |   minimum_all_step_improvement_pct |   roi_x |   roi_y |   roi_width |   roi_height |
|:---------|:----------------------------|:--------------|:-----------------------|:-----------------|:-----------------------|--------------------:|:-------------------------|----------------------------------:|-----------------------------------:|--------:|--------:|------------:|-------------:|
| 50x      | 50x_x0592_y0032_w0360_h0320 | robust_common | True                   | True             | True                   |                  19 | True                     |                          18.139   |                         28.1863    |     592 |      32 |         360 |          320 |
| 20x      | 20x_x0592_y0752_w0360_h0320 | not_common    | False                  | False            | False                  |                  12 | True                     |                          -9.59361 |                         31.0022    |     592 |     752 |         360 |          320 |
| 5x       | 5x_x1432_y0512_w0360_h0320  | not_common    | True                   | False            | False                  |                  18 | False                    |                          -2.49941 |                         -0.0608837 |    1432 |     512 |         360 |          320 |

## Locked ROIs

| family   | dataset         | groups            | candidate_id                | common30_pass   | strict_four_fold_pass   | strict_four_fold_candidate   |   roi_x |   roi_y |   roi_width |   roi_height |   min_common30_improvement_pct |   median_common30_improvement_pct |   min_fold_improvement_pct |
|:---------|:----------------|:------------------|:----------------------------|:----------------|:------------------------|:-----------------------------|--------:|--------:|------------:|-------------:|-------------------------------:|----------------------------------:|---------------------------:|
| 50x      | 20260702_100MG  | x_0p5um;x_1um     | 50x_x0592_y0032_w0360_h0320 | True            | True                    | 50x_x0592_y0032_w0360_h0320  |     592 |      32 |         360 |          320 |                       27.1714  |                          46.2164  |                    16.9283 |
| 20x      | 20260704_20x_5x | 20x_0p5um;20x_1um | 20x_x0592_y0752_w0360_h0320 | False           | False                   |                              |     592 |     752 |         360 |          320 |                       56.4351  |                          57.6029  |                    11.978  |
| 5x       | 20260704_20x_5x | 5x_0p5um;5x_1um   | 5x_x1432_y0512_w0360_h0320  | True            | False                   |                              |    1432 |     512 |         360 |          320 |                        1.08182 |                           1.50175 |                   -10.3855 |

## Raw versus V42

| selection         | family   | dataset         | group     |   n_common_valid |   raw_step_sd_nm |   v42_step_sd_nm |   v42_improvement_pct |   raw_mean_bias_nm |   v42_mean_bias_nm |   raw_rmse_nm |   v42_rmse_nm |   raw_localization_nm |   v42_localization_nm | v42_more_stable   |
|:------------------|:---------|:----------------|:----------|-----------------:|-----------------:|-----------------:|----------------------:|-------------------:|-------------------:|--------------:|--------------:|----------------------:|----------------------:|:------------------|
| search_common30   | 50x      | 20260702_100MG  | x_0p5um   |               30 |         17.2424  |          5.98979 |            65.2614    |         -39.913    |          -18.6724  |      43.364   |       19.579  |               143.435 |               38.6552 | True              |
| search_common30   | 50x      | 20260702_100MG  | x_1um     |               30 |         22.2374  |         16.1952  |            27.1714    |         -27.9332   |          -17.8467  |      35.4723  |       23.9175 |               291.966 |               82.3325 | True              |
| search_common30   | 20x      | 20260704_20x_5x | 20x_0p5um |               30 |         38.1881  |         15.7447  |            58.7707    |           4.89402  |           48.1263  |      37.8639  |       50.5546 |               169.649 |               98.6084 | True              |
| search_common30   | 20x      | 20260704_20x_5x | 20x_1um   |               19 |         82.8714  |         36.1029  |            56.4351    |          81.8632   |          171.703   |     114.925   |      175.262  |               198.554 |              115.687  | True              |
| search_common30   | 5x       | 20260704_20x_5x | 5x_0p5um  |               30 |          6.71162 |          6.58265 |             1.92168   |          -4.47283  |           -2.55913 |       7.97186 |        6.9596 |               371.827 |              234.757  | True              |
| search_common30   | 5x       | 20260704_20x_5x | 5x_1um    |               30 |         59.3639  |         58.7217  |             1.08182   |         -53.9093   |          -53.8447  |      79.4532  |       78.9465 |               372.087 |              236.823  | True              |
| heldout_remaining | 50x      | 20260702_100MG  | x_0p5um   |               19 |         28.0965  |         23       |            18.139     |         -38.8688   |          -16.9789  |      47.5252  |       28.097  |               149.644 |               38.4358 | True              |
| heldout_remaining | 50x      | 20260702_100MG  | x_1um     |               19 |         32.7749  |         23.2437  |            29.0808    |         -29.0485   |          -19.7881  |      43.1448  |       30.0567 |               289.01  |              131.797  | True              |
| heldout_remaining | 20x      | 20260704_20x_5x | 20x_0p5um |               17 |         34.1803  |         37.4594  |            -9.59361   |          -6.2121   |           46.4724  |      33.7366  |       58.9945 |               168.64  |              108.662  | False             |
| heldout_remaining | 20x      | 20260704_20x_5x | 20x_1um   |               12 |        103.093   |         80.2666  |            22.1414    |          62.3154   |          155.452   |     116.729   |      173.41   |               170.011 |              109.433  | True              |
| heldout_remaining | 5x       | 20260704_20x_5x | 5x_0p5um  |               19 |         11.679   |         11.9709  |            -2.49941   |          12.8699   |           13.617   |      17.1713  |       17.9216 |               369.583 |              231.688  | False             |
| heldout_remaining | 5x       | 20260704_20x_5x | 5x_1um    |               18 |        154.017   |        153.356   |             0.429105  |        -234.05     |         -235.634   |     277.818   |      278.81   |               374.531 |              231.488  | True              |
| all_steps         | 50x      | 20260702_100MG  | x_0p5um   |               49 |         21.8154  |         14.8576  |            31.8943    |         -39.5081   |          -18.0157  |      45.0232  |       23.2553 |               143.713 |               38.6249 | True              |
| all_steps         | 50x      | 20260702_100MG  | x_1um     |               49 |         26.4931  |         19.0257  |            28.1863    |         -28.3657   |          -18.5995  |      38.6287  |       26.4676 |               289.01  |               98.7667 | True              |
| all_steps         | 20x      | 20260704_20x_5x | 20x_0p5um |               47 |         36.8082  |         25.3968  |            31.0022    |           0.876912 |           47.5281  |      36.425   |       53.7605 |               169.416 |              104.517  | True              |
| all_steps         | 20x      | 20260704_20x_5x | 20x_1um   |               31 |         90.0626  |         56.6492  |            37.1002    |          74.2963   |          165.412   |     115.627   |      174.547  |               191.826 |              113.152  | True              |
| all_steps         | 5x       | 20260704_20x_5x | 5x_0p5um  |               49 |         12.2986  |         11.9721  |             2.65452   |           2.25191  |            3.71325 |      12.379   |       12.4175 |               371.568 |              233.207  | True              |
| all_steps         | 5x       | 20260704_20x_5x | 5x_1um    |               48 |        136.095   |        136.178   |            -0.0608837 |        -121.462    |         -122.016   |     181.353   |      181.785  |               372.375 |              234.537  | False             |
