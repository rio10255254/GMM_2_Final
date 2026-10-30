# Lab R48 Real-Corner Data - 2026-06-13

## Purpose

R48 was created after R47 failed on the real `20250605_checkboard` corner
validation. The goal is to make the Lab training data closer to the real
corner failure mode and to give the trainer explicit boundary geometry
sidecars instead of relying only on image appearance.

## New Clean GT Stages

| Stage | Count | Role |
|---|---:|---|
| `stage_53_real_corner_anchor` | 1900 | large checkboard-like corners and corner anchors |
| `stage_54_lattice_intersection_anchor` | 1100 | grid intersections and thin hard edges |
| `stage_55_real_texture_corner` | 1300 | real Lab checkboard texture/background with synthetic precise corners |
| `stage_56_corner_psf_stress` | 700 | hard-corner stress cases for PSF blur and noise |

Total new clean GT images: 5000.

## PSF Blur

The shared Lab `Training_Data/PSF_Convolution.py` script was reused. Only
stages 53-56 were convolved in this R48 pass.

Run controls:

- `LAB_RUN_STAGE_IDS=53,54,55,56`
- `LAB_NOISE_SEED=4848`
- Lab PSF: `psf_calibration/results/20250605_inner_circle_roi_fine_prealign_fit/PSF_fitted_2D_FOVstack.mat`

## Packages

| Package | Total pairs | Ring | Shape | Micro | Boundary | Real texture |
|---|---:|---:|---:|---:|---:|---:|
| `r48_real_corner_train_6000` | 6000 | 800 | 700 | 700 | 3000 | 800 |
| `real_corner_val_unseen` | 1200 | 0 | 0 | 0 | 700 | 500 |

Every packaged source image has three sidecars under the package `geom/`
folder:

- `boundary/`
- `centerline/`
- `distance/`

## Verification

| Check | Result |
|---|---|
| Split validation | passed |
| Unit tests | 6 passed |
| Train package src/lbl/geometry counts | 6000 each |
| Held-out package src/lbl/geometry counts | 1200 each |
| Dry run | passed |
| 1-epoch smoke training | passed |
| 4-epoch geometry smoke training | passed; boundary geometry loss became nonzero after warmup |

## Preview

Clean preview:

`Training_Data/reports/r48_real_corner_preview.png`

## Current Status

The first formal R48 R39-start 200-epoch training run was launched after data
verification. Its results should be evaluated with real checkboard
reconstruction and the same corner-geometry validation used for R46/R47.
