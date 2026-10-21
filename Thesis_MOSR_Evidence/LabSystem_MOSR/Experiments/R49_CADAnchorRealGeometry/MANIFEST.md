# R49_CADAnchorRealGeometry Manifest

Last updated: 2026-08-10

## Identity

| Item | Value |
|---|---|
| Lab line | R49_CADAnchorRealGeometry |
| Scope | Lab CAD-anchor real-checkboard geometry transfer with geometry sidecars |
| Status | Completed negative result; 100-epoch training finished, real checkboard validation failed |
| Motivation | R48 did not solve the real rounded-corner problem on the Lab checkboard sequence |
| Storage status | Full history archived and hash-verified on H; thin canonical context retained on D |

## Canonical Files

| Item | Status | Location |
|---|---|---|
| R49 data builder | ready | `scripts/r49_cad_anchor_data.py` |
| R49 training launcher | ready | `scripts/launch_r49.py` |
| Tests | passing | `tests/` |
| CAD-anchor preview | completed | `../../Training_Data/reports/r49_cad_anchor_preview.png` |
| Training package | completed | `../../Training_Data/r49_cad_anchor_real_geometry/r49_cad_anchor_train_4000/` |
| Held-out validation package | completed | `../../Training_Data/r49_cad_anchor_real_geometry/cad_anchor_val_real/` |
| Formal 100-epoch run | completed | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r49_cad_anchor_r40_tradeoff_e100_cad_anchor_r40_20260614_145324/` |
| R49 results report | completed | `reports/R49_RESULTS_20260614.md` |
| R49 real checkboard validation | completed; failed | `reports/R49_CHECKBOARD_VALIDATION_20260614.md` |
| R49 failure analysis | completed | `reports/R49_FAILURE_ANALYSIS_20260614.md` |
| Archive restore pointer | completed | `ARCHIVE_POINTER_R49_20260809.md` |
| Exact archive scope | completed | `ARCHIVE_SCOPE_R49_20260809.json` |
| Exact cleanup plan and result | completed | `ARCHIVE_DELETE_PLAN_R49_20260809.json` |
| Re-runnable cleanup verifier | completed | `scripts/execute_r49_archive_cleanup.ps1` |

## Verification

| Check | Result |
|---|---|
| Unit tests | 3 passed before archive and 3 passed after D-drive cleanup |
| Valid CAD source pairs | 36 |
| CAD-anchor source patches | train 408, val 120, test 48 |
| Train package pairs | 4000 |
| Held-out validation pairs | 120 |
| Train/validation split overlap | none |
| Package src/lbl counts | train 4000/4000, validation 120/120 |
| Geometry sidecars | train 4000 boundary + centerline + distance; validation 120 boundary + centerline + distance |
| Dry run | passed; Lab PSF and geometry sidecar path mounted |
| Smoke training | passed; 1 epoch, 1 train batch |
| Formal training | completed to epoch 100 |
| Best internal epoch | epoch 50 |
| Real checkboard reconstruction cases | latest, best_tradeoff, best_detail_guarded; 51 frames each |
| Best R49 real-corner median shift | 9.000 px |
| Previous best Lab control median shift | 4.243 px |
| Best R48 median shift | 6.708 px |
| R49 real-corner verdict | failed; not promotable |

## Archive Verification

| Check | Result |
|---|---|
| Full-history snapshot | `H:\GMM_2_Final_Archive\lab_system\R49_CADAnchorRealGeometry\20260809_full_history\snapshot` |
| Snapshot scope before final context refresh | 13 source directories; 22,751 files; 11.1838 GiB |
| SHA-256 manifests | 13 files matching `H:\GMM_2_Final_Archive\manifests\Lab_R49_*_20260809.csv` |
| Verification before D cleanup | PASS; no missing or mismatched files |
| Exact D cleanup | 62 targets; 22,694 files; 11.1686 GiB logical |
| Physical D space reclaimed | 8.7816 GiB |
| Verification after D cleanup | PASS; no missing or mismatched files |
| Restore dependency | Restore `Training_Data/r49_cad_anchor_source` before rebuilding R53 |

## Handoff

Do not promote R49. The formal run completed and was reconstructed on the real
`20250605_checkboard` sequence, but all tested R49 checkpoints failed the
real-corner validation. The result shows that a small masked CAD-anchor slice
does not solve the corner-rounding problem and can make the corner response move
even farther from the raw checker corner.
