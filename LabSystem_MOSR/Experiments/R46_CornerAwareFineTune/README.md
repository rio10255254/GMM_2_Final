# R46_CornerAwareFineTune

Lab-system corner/checkboard data and conservative fine-tune entry point.

This Lab R46 line keeps the useful lesson from the main project R46 work:
corner and right-angle coverage matter, but aggressive high-frequency tuning can
damage displacement stability. The Lab variant therefore adds a dedicated
checkboard/corner data family first, then provides a conservative launcher that
starts from the Lab R39 validation-quality checkpoint.

## Current Status

Data preparation, smoke validation, and the first formal 25-epoch training run
are complete. Reconstruction validation was also run on the real Lab checkboard
sequence. The run is valid, but it did not fix the rounded-corner problem, so
R46 is not ready for promotion as the Lab recommendation.

## Data

| Package | Role | Pairs |
|---|---|---:|
| `r46_checkboard_corner_train` | Training mix: ring replay + R39 shapes + R40 micro + Lab checkboard corners | 1550 |
| `checkboard_corner_val_unseen` | Held-out Lab checkboard/corner validation | 100 |

The clean checkboard/corner GT is stored as stage 48 under the Lab
`Training_Data/generated/` tree. The materialized package places corner samples
under a boundary-compatible package path so the existing trainer can infer a
known role without modifying the shared model trainer.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/r46_corner_data.py` | Generate clean checkboard/corner GT, build train/val packages, validate splits, create preview. |
| `scripts/launch_r46.py` | Conservative Lab R46 fine-tune launcher using the new data package. |

## Results

The data report is in:

`Training_Data/reports/LAB_R46_CHECKBOARD_CORNER_DATA_20260612.md`

The successful smoke run is:

`Experiments/Training_Runs/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_111237/`

The formal training report is:

`Experiments/R46_CornerAwareFineTune/reports/R46_RESULTS_20260612.md`

The first formal training run is:

`Experiments/Training_Runs/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_112100/`

The post-training corner validation report is:

`Experiments/reports/LAB_R46_CHECKBOARD_CORNER_VALIDATION_20260612.md`

## Next Step

Revise the checkboard/corner data domain before longer training. The current
R46 candidates are useful evidence, but not a better real-checkboard solution.
