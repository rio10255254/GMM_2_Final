# R51_BlurSourceProbe Manifest

Last updated: 2026-06-14

## Identity

| Item | Value |
|---|---|
| Lab line | R51_BlurSourceProbe |
| Scope | Lab Gaussian / weak-BADS / mixed-PSF blur-source training probe |
| Status | Completed directional probe; not promoted |
| Motivation | R50 found formal BADS usable but too soft as the only checkboard-corner blur truth |

## Canonical Files

| Item | Status | Location |
|---|---|---|
| R51 data builder | ready | `scripts/r51_blur_source_data.py` |
| R51 training launcher | ready | `scripts/launch_r51.py` |
| R51 reconstruction launcher | ready | `scripts/run_r51_checkboard_reconstruction.py` |
| Tests | passing | `tests/` |
| Gaussian probe package | completed | `../../Training_Data/r51_blur_source_probe/r51_gaussian_corner_probe/` |
| Weak-BADS probe package | completed | `../../Training_Data/r51_blur_source_probe/r51_weak_bads_corner_probe/` |
| Mixed-PSF probe package | completed | `../../Training_Data/r51_blur_source_probe/r51_mixed_psf_corner_probe/` |
| Held-out mixed corner validation package | completed | `../../Training_Data/r51_blur_source_probe/r51_mixed_corner_val/` |
| Gaussian short training run | completed | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_gaussian_corner_probe_short_e012_b080_20260614_215954/` |
| Weak-BADS short training run | completed | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_weak_bads_corner_probe_short_e012_b080_20260614_220314/` |
| Mixed-PSF short training run | completed | `../../Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_mixed_psf_corner_probe_short_e012_b080_20260614_220602/` |
| R51 checkboard reconstruction outputs | completed | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/r51_reconstruction_outputs/` |
| R51 GMF-ready cases | completed | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/gmf_cases/lab_r51_*/` |
| R51 results report | completed | `reports/R51_RESULTS.md` |
| R51 real checkboard validation | completed | `reports/R51_CHECKBOARD_VALIDATION.md` |
| R51 validation artifacts | completed | `../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/corner_geometry_validation_r51_20260614/` |

## Verification

| Check | Result |
|---|---|
| Unit tests | 6 passed |
| Package split validation | passed |
| Probe packages | 3 train packages, 1550 pairs each |
| Held-out validation package | 100 pairs |
| Dry run | passed; three R51 candidates discovered |
| Smoke training | passed; 1 epoch / 1 train batch |
| Short training | completed for Gaussian, weak-BADS, and mixed-PSF probes |
| Reconstruction cases | 6 R51 cases, 51 frames each |
| Filename identity against raw sequence | true for all R51 cases |
| Raw accepted corners | 358 |
| Previous Lab R40 median corner shift | 4.243 px |
| Best R51 median corner shift | 2.828 px, mixed-PSF best_tradeoff |
| Previous Lab R40 large-shift corner rate | 24.581% |
| Best R51 large-shift corner rate | 36.872%, mixed-PSF best_tradeoff |
| R51 verdict | directional improvement only; not promotable |

## Handoff

Do not promote R51 as a Lab model replacement. The mixed-PSF probe is the best
directional candidate because it reduces the typical corner displacement on the
real checkboard sequence, but it still leaves too many corners with large
movement. The next Lab round should reuse the mixed-PSF data direction and add a
real-corner stability guard rather than treating synthetic loss alone as the
selection target.
