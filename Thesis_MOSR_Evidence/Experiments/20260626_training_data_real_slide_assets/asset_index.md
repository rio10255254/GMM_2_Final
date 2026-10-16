# 20260626 Real Slide Assets

This folder collects slide-ready assets for the R61 v16 training-data and validation story.

## Figures
- `01_training_real_sem_truth_anchor_examples.png`
- `02_training_real_sequence_guard_examples.png`
- `03_training_motion_synthetic_pair_example.png`
- `04_100mg_sem_reference_contact_sheet.png`
- `05_step_real_reconstruction_raw_old_new_contact.png`
- `06_100mg_real_reconstruction_raw_old_v16_center_crop.png`
- `07_100mg_center12_pillar_cd_position_line.png`
- `07b_100mg_center12_pillar_cd_raw_v16_truth_line.png`
- `08_100mg_all_sem_truthed_pillar_cd_position_line.png`
- `09_step_displacement_1um_position_line.png`
- `10_step_displacement_0p5um_position_line.png`

## Numeric checks
- 100MG center 12 SEM-truthed pillars: R61 v16 is closer than Raw on 4 / 12 points.
- 100MG center 12 SEM-truthed pillars: R61 v16 is equal to Raw on 3 / 12 points and worse on 5 / 12 points.
- 100MG center 12 SEM-truthed pillars: R61 v16 is closer than old R57 on 12 / 12 points.
- Center 12 MAE: Raw 22.51 nm, old R57 81.17 nm, R61 v16 20.50 nm.
- 1.0 um Step MAE: Raw 0.02068 um, R61 v16 0.01414 um.
- 0.5 um Step MAE: Raw 0.02012 um, R61 v16 0.01402 um.

## Tables
- `100mg_center12_sem_truthed_pillar_cd.csv`
- `100mg_sem_truthed_pillar_cd_all_clean.csv`
- `09_step_displacement_1um_position_line.csv`
- `10_step_displacement_0p5um_position_line.csv`
- `summary.json`
