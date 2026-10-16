# R48_RealCornerTransfer Manifest

Last updated: 2026-08-01

## Identity

| Item | Value |
|---|---|
| Lab line | R48_RealCornerTransfer |
| Scope | Lab real-checkboard corner transfer with geometry sidecars |
| Status | Completed negative result; 200-epoch training finished, real checkboard validation failed |
| Motivation | R47 did not solve the real rounded-corner problem on the Lab checkboard sequence |

## Storage Status (2026-08-01)

The complete R48 payload is stored at
`H:\GMM_2_Final_Archive\lab_system\R48_RealCornerTransfer\20260801_full_history`.
Thirteen SHA-256 manifests passed before and after D-drive cleanup. D retains
the two data manifests, training logs and curves, canonical reports, scripts,
tests, corner evidence and restore pointers. Exact scope and restore mapping:
`ARCHIVE_SCOPE_R48_20260801.json` and `ARCHIVE_POINTER_R48_20260801.md`.

## Canonical Files

| Item | Status | Location |
|---|---|---|
| R48 data builder | ready | `scripts/r48_real_corner_data.py` |
| R48 training launcher | ready | `scripts/launch_r48.py` |
| Tests | passing | `tests/` |
| Clean preview | completed | `../../Training_Data/reports/r48_real_corner_preview.png` |
| Training package | full payload archived; manifest on D | `../../Training_Data/r48_real_corner_transfer/r48_real_corner_train_6000/` |
| Held-out validation package | full payload archived; manifest on D | `../../Training_Data/r48_real_corner_transfer/real_corner_val_unseen/` |
| Smoke training runs | full weights archived; logs and curves on D | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r48_real_corner_r39_latest_smoke_*/` |
| First formal 200-epoch run | full weights archived; logs and curves on D | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r48_real_corner_r39_latest_20260613_163644/` |
| Formal resume run | full weights archived; logs and curves on D | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r48_real_corner_r39_latest_resume_e120_to200_20260613_235726/` |
| R48 results report | completed | `reports/R48_RESULTS_20260614.md` |
| R48 real checkboard validation | completed; failed | `reports/R48_CHECKBOARD_VALIDATION_20260613.md` |

## Verification

| Check | Result |
|---|---|
| Unit tests | 16 passed (post-archive verification, 2026-08-01) |
| Clean GT count | 5000 |
| BADS PSF convolved count | 5000 |
| Lab PSF stack | 25 PSFs from fitted Lab FOV grid |
| Train package pairs | 6000 |
| Held-out validation pairs | 1200 |
| Train/validation split overlap | none |
| Package src/lbl counts | train 6000/6000, validation 1200/1200 |
| Geometry sidecars | train 6000 boundary + centerline + distance; validation 1200 boundary + centerline + distance |
| New-stage image format | 512 x 512, uint8 |
| Dry run | passed; Lab PSF and geometry sidecar path mounted |
| Smoke training | passed; boundary geometry loss activated at epoch 4 |
| Formal training | completed to epoch 200 |
| Real checkboard reconstruction cases | latest, best_tradeoff, best_detail_guarded; 51 frames each |
| Best R48 real-corner median shift | 6.708 px |
| Previous best Lab control median shift | 4.243 px |
| R48 real-corner verdict | failed; not promotable |

## Handoff

Do not promote R48. The formal run completed and was reconstructed on the real
`20250605_checkboard` sequence, but all tested R48 checkpoints failed the
real-corner validation. The result shows that geometry-aware synthetic
real-corner training alone did not fix the corner rounding seen in R46/R47.
