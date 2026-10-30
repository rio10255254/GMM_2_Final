# R46_CornerAwareFineTune Manifest

Last updated: 2026-06-12

## Identity

| Item | Value |
|---|---|
| Lab line | R46_CornerAwareFineTune |
| Scope | Lab checkboard/corner training-data extension and conservative fine-tune entry point |
| Status | Formal 25-epoch training completed; real checkboard corner validation did not pass |
| Main-project reference | R46_CornerAwareFineTune failure diagnosis, reused as a caution rather than copied as-is |

## Canonical Files

| Item | Status | Location |
|---|---|---|
| Corner data builder | ready | `scripts/r46_corner_data.py` |
| R46 launcher | ready | `scripts/launch_r46.py` |
| Tests | passing | `tests/` |
| Data report | completed | `../../Training_Data/reports/LAB_R46_CHECKBOARD_CORNER_DATA_20260612.md` |
| Data summary JSON | completed | `../../Training_Data/reports/r46_checkboard_corner_data_summary.json` |
| Preview | completed | `../../Training_Data/reports/r46_checkboard_corner_preview.png` |
| Training package | completed | `../../Training_Data/r46_corner_aware_finetune/r46_checkboard_corner_train/` |
| Held-out validation package | completed | `../../Training_Data/r46_corner_aware_finetune/checkboard_corner_val_unseen/` |
| Smoke run | completed | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_111237/` |
| Formal training report | completed | `reports/R46_RESULTS_20260612.md` |
| Formal training run | completed | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r46_checkboard_corner_r39_latest_20260612_112100/` |
| Formal training stdout/stderr | completed | `results/formal_training_20260612/` |
| R46 checkboard reconstruction outputs | completed | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/reconstruct_progress_*_in_20250605_checkboard_20260612_112100/` |
| R46 external GMF case folders | completed | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r46_*/` |
| R46 corner validation report | completed; did not pass | `../reports/LAB_R46_CHECKBOARD_CORNER_VALIDATION_20260612.md` |

## Verification

| Check | Result |
|---|---|
| Unit tests | 5 passed |
| Clean GT count | 500 |
| BADS PSF convolved count | 500 |
| Gaussian control count | 500 |
| Train package pairs | 1550 |
| Held-out validation pairs | 100 |
| Train/validation split overlap | none |
| Launcher dry-run | passed |
| Smoke training | passed: 1 epoch, 1 train batch |
| Formal training | passed: 25 epochs |
| Formal checkpoints | final epoch 25, best tradeoff epoch 17, detail-guarded epoch 15 |
| Formal validation log | epochs 1-25 recorded |
| Formal monitor BMPs | epochs 1, 5, 10, 15, 20, 25 nonblank |
| R46 reconstruction packages | 3 cases, 51 frames each, filename identity preserved |
| Real checkboard corner validation | failed to improve over R40 tradeoff |

## Handoff

The first formal run and reconstruction validation are complete. Keep the R46
checkpoints and GMF cases for traceability, but do not promote R46 as the Lab
recommendation. The next useful work is to revise the corner/checkboard data
domain before longer training.
