# ROI visual audit index

Each dataset folder follows the same sequence:

1. `01_full_frame_overlays`: the exact three ROI rectangles on Raw, V41, and V42.
2. `02_individual_roi_crops`: individual reference crops used by the detector.
3. `03_roi_case_comparisons`: Raw/V41/V42 crop comparison.
4. `04_edge_selection`: candidate and actually used frozen-V41 edge positions.
5. `05_reference_next_pair`: reference and next-frame process view for all three cases.
6. `06_edge_profiles`: one representative shared edge shown as intensity and slope profiles.

## ROI coordinates

| dataset         | group     | roi_name               | roi_label                     |   roi_x |   roi_y |   roi_width |   roi_height |
|:----------------|:----------|:-----------------------|:------------------------------|--------:|--------:|------------:|-------------:|
| 20260702_100MG  | x_0p5um   | legacy_cross           | A Legacy cross-pattern ROI    |     690 |     460 |         739 |          744 |
| 20260702_100MG  | x_0p5um   | clean_pillar_grid      | B Clean pillar-grid ROI       |    1050 |      90 |         700 |          560 |
| 20260702_100MG  | x_0p5um   | clean_vertical_lines   | C Clean vertical-line ROI     |     100 |      90 |         700 |          560 |
| 20260702_100MG  | x_1um     | legacy_cross           | A Legacy cross-pattern ROI    |     685 |     453 |         746 |          758 |
| 20260702_100MG  | x_1um     | clean_pillar_grid      | B Clean pillar-grid ROI       |    1050 |      90 |         700 |          560 |
| 20260702_100MG  | x_1um     | clean_vertical_lines   | C Clean vertical-line ROI     |     100 |      90 |         700 |          560 |
| 20260704_20x_5x | 20x_0p5um | legacy_cross           | A Legacy cross-pattern ROI    |     259 |     607 |         494 |          473 |
| 20260704_20x_5x | 20x_0p5um | clean_pillar_grid      | B Clean pillar-grid ROI       |     520 |     100 |         650 |          540 |
| 20260704_20x_5x | 20x_0p5um | clean_vertical_lines   | C Clean vertical-line ROI     |     520 |     880 |         620 |          450 |
| 20260704_20x_5x | 20x_1um   | legacy_cross           | A Legacy cross-pattern ROI    |     260 |     607 |         504 |          528 |
| 20260704_20x_5x | 20x_1um   | clean_pillar_grid      | B Clean pillar-grid ROI       |     520 |     100 |         650 |          540 |
| 20260704_20x_5x | 20x_1um   | clean_vertical_lines   | C Clean vertical-line ROI     |     520 |     880 |         620 |          450 |
| 20260704_20x_5x | 5x_0p5um  | legacy_cross           | A Legacy cross-pattern ROI    |     964 |     454 |         725 |          725 |
| 20260704_20x_5x | 5x_0p5um  | clean_outer_grid       | B Clean outer-grid ROI        |    1280 |     120 |         480 |          300 |
| 20260704_20x_5x | 5x_0p5um  | clean_center_microgrid | C Clean center micro-grid ROI |    1320 |     850 |         300 |          280 |
| 20260704_20x_5x | 5x_1um    | legacy_cross           | A Legacy cross-pattern ROI    |     960 |     454 |         721 |          725 |
| 20260704_20x_5x | 5x_1um    | clean_outer_grid       | B Clean outer-grid ROI        |    1280 |     120 |         480 |          300 |
| 20260704_20x_5x | 5x_1um    | clean_center_microgrid | C Clean center micro-grid ROI |    1320 |     850 |         300 |          280 |