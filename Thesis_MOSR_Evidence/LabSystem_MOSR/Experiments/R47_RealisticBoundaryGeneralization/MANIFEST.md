# R47_RealisticBoundaryGeneralization Manifest

Last updated: 2026-06-13

## Identity

| Item | Value |
|---|---|
| Lab line | R47_RealisticBoundaryGeneralization |
| Scope | Lab training-data expansion for generalized precise boundary reconstruction |
| Status | Data generated and validated; 200-epoch formal training complete; real checkboard validation completed and failed |
| Motivation | R46 ideal checkboard/corner data did not transfer cleanly to real Lab checkboard corners |

## Canonical Files

| Item | Status | Location |
|---|---|---|
| R47 data builder | ready | `scripts/r47_realistic_boundary_data.py` |
| Tests | passing | `tests/` |
| Data report | completed | `../../Training_Data/reports/LAB_R47_REALISTIC_BOUNDARY_DATA_20260612.md` |
| Clean preview | completed | `../../Training_Data/reports/r47_realistic_boundary_clean_preview.png` |
| Convolved preview | completed | `../../Training_Data/reports/r47_realistic_boundary_convolved_preview.png` |
| Training package | completed | `../../Training_Data/r47_realistic_boundary_generalization/r47_realistic_boundary_train_4000/` |
| Held-out validation package | completed | `../../Training_Data/r47_realistic_boundary_generalization/realistic_boundary_val_unseen/` |
| 200-epoch training report | completed | `reports/R47_RESULTS_20260613.md` |
| Real checkboard validation report | completed; negative result | `reports/R47_CHECKBOARD_VALIDATION_20260613.md` |
| Formal 200-epoch run | completed | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r47_realistic_boundary_r39_latest_20260612_171140/` |
| Conservative checkpoint | completed; selected by trainer | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r47_realistic_boundary_r39_latest_20260612_171140/weights/best_tradeoff.pth.tar` |
| Final checkpoint | completed; tested on real checkboard and not promoted | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r47_realistic_boundary_r39_latest_20260612_171140/weights/latest.pth.tar` |
| R47 epoch 33 reconstruction output | completed; 51 frames | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/reconstruct_progress_best_tradeoff_in_20250605_checkboard_20260612_171140/lab_r47_best_tradeoff/` |
| R47 epoch 200 reconstruction output | completed; 51 frames | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/reconstruct_progress_latest_in_20250605_checkboard_20260612_171140/lab_r47_latest/` |
| R47 external GMF cases | prepared; no GMF_score.txt present yet | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r47_*/` |
| R47 corner validation artifacts | completed | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r47_20260613/` |

## Verification

| Check | Result |
|---|---|
| Unit tests | 7 passed |
| Clean GT count | 2700 |
| BADS PSF convolved count | 2700 |
| Lab PSF stack | 25 PSFs from a 5 x 5 fitted FOV grid |
| Train package pairs | 4000 |
| Held-out validation pairs | 800 |
| Train/validation split overlap | none |
| Package src/lbl counts | train 4000/4000, validation 800/800 |
| New-stage image format | 512 x 512, uint8 |
| Input/label pair difference | nonzero on sampled stages |
| 200-epoch training | completed |
| Best checkpoint | epoch 33 `best_tradeoff.pth.tar` |
| Final checkpoint | epoch 200 `latest.pth.tar` |
| Real checkboard reconstructions | epoch 33 and epoch 200 completed, 51 frames each |
| R47 external GMF package | prepared, filenames preserved, external scores pending |
| Real checkboard corner validation | failed; R47 should not be promoted |

## Handoff

R47 should not be treated as a usable Lab reconstruction result. The completed
real checkboard validation shows that both R47 checkpoints still damage corner
geometry, with epoch 33 worse than epoch 200. The next line should revise the
training target and selection guard instead of continuing the same R47 setup.
