# R52_CornerStabilityGuard Manifest

Last updated: 2026-08-24

## Identity

| Item | Value |
|---|---|
| Lab line | R52_CornerStabilityGuard |
| Scope | Lab mixed-PSF plus real-corner stability formal training |
| Status | Completed; not promoted |
| Motivation | R51 improved typical corner shift but increased the large-shift corner rate |

## Canonical Files

| Item | Status | Location |
|---|---|---|
| R52 data builder | ready | `scripts/r52_corner_stability_data.py` |
| R52 training launcher | ready | `scripts/launch_r52.py` |
| R52 corner gate | ready | `scripts/r52_corner_gate.py` |
| R52 reconstruction launcher | ready | `scripts/run_r52_checkboard_reconstruction.py` |
| Tests | passing | `tests/` |
| Formal training package | archived; restore before use | `H:\GMM_2_Final_Archive\lab_system\R52_CornerStabilityGuard\20260813_full_history\snapshot\Training_Data\r52_corner_stability_guard\r52_corner_stability_train_4000\` |
| Held-out validation package | archived; restore before use | `H:\GMM_2_Final_Archive\lab_system\R52_CornerStabilityGuard\20260813_full_history\snapshot\Training_Data\r52_corner_stability_guard\r52_corner_stability_val\` |
| Smoke training run | archived; compact evidence remains on D | `results/archive_retained_20260813/smoke_run_evidence/` |
| Formal 100-epoch run | archived; logs and three representative checkpoints remain on D | `results/archive_retained_20260813/formal_run_evidence/` |
| Formal run PID/log pointer | completed | `results/r52_formal_e100_20260614_225412.pid.txt` |
| R52 reconstructed checkboard cases | archived; restore before use | H-drive snapshot, see `ARCHIVE_POINTER_R52_20260813.md` |
| R52 GMF-ready case folders | archived; restore before use | H-drive snapshot, see `ARCHIVE_POINTER_R52_20260813.md` |
| R52 real checkboard validation | failed gate | `reports/R52_CHECKBOARD_VALIDATION.md` |
| R52 status report | completed | `reports/R52_RESULTS.md` |
| D-drive compact evidence | hash-verified | `results/archive_retained_20260813/` |
| Full historical snapshot | eight sources hash-verified; final 23,858 files / 11.870 GiB | `H:\GMM_2_Final_Archive\lab_system\R52_CornerStabilityGuard\20260813_full_history\snapshot` |
| Archive and restore entry | ready | `ARCHIVE_POINTER_R52_20260813.md` |
| Exact removal plan and result | completed and verified | `ARCHIVE_DELETE_PLAN_R52_20260813.json` |
| Final archive execution | completed and verified | `ARCHIVE_EXECUTION_R52_20260824.json` |

## Verification

| Check | Result |
|---|---|
| Unit tests | 6 passed |
| Package split validation | passed |
| Formal train package | 4000 pairs |
| Held-out validation package | 700 pairs |
| Geometry sidecars | 4000 train + 700 validation |
| Training dry-run | passed |
| Smoke training | passed; 1 epoch / 1 train batch |
| Formal training | completed; 100 epochs |
| Real checkboard reconstruction | completed; 51 frames x 2 checkpoints |
| Real corner gate | failed |

## Handoff

R52 is completed but not promoted. The epoch-100 `latest` checkpoint improved
median real-corner shift versus Lab R40, but it still increased the large-shift
corner rate. The full data, training and reconstruction history has a verified
H-drive snapshot; D retains reports, code, tests, manifests, three representative
checkpoints and the complete corner-validation evidence. Restore the full image
folders before any external GMF follow-up. Do not use R52 as the Lab model baseline.
