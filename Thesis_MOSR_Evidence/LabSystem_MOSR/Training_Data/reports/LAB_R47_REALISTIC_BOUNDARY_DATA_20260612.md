# Lab R47 Realistic Boundary Data - 2026-06-12

## What Was Built

R47 expands the Lab training data to a 4000-pair training package aimed at
better boundary generalization. It keeps the existing ring, shape, and
microstructure coverage, then adds more realistic hard-boundary samples.

This is a data package only. No R47 model has been trained yet.

## New Clean GT Stages

| Stage | Count | Purpose |
|---|---:|---|
| `stage_49_realistic_checkboard_corners` | 800 | Dense checkboard and hard right-angle corners |
| `stage_50_intersections_edges` | 600 | T/cross intersections, bars, and mixed straight edges |
| `stage_51_real_background_boundaries` | 900 | Crisp boundary GT over low-frequency style extracted from the real Lab checkboard sequence |
| `stage_52_boundary_psf_stress` | 400 | Thin/high-frequency boundary cases that stress blur compensation |

Total new clean GT: 2700 images.

## PSF/Blur Pair Generation

The blurry inputs were generated through the shared Lab PSF convolution script.
The actual fitted Lab PSF file contains a 5 x 5 grid, so 25 PSFs were loaded.
Within each new stage, images cycle through these 25 PSFs, then receive
Poisson-Gaussian camera noise.

| Stage | Clean GT | Convolved input | Image format |
|---|---:|---:|---|
| `stage_49_realistic_checkboard_corners` | 800 | 800 | 512 x 512, uint8 |
| `stage_50_intersections_edges` | 600 | 600 | 512 x 512, uint8 |
| `stage_51_real_background_boundaries` | 900 | 900 | 512 x 512, uint8 |
| `stage_52_boundary_psf_stress` | 400 | 400 | 512 x 512, uint8 |

## Training Package Mix

| Role | Pairs |
|---|---:|
| Ring replay | 700 |
| Existing shape coverage | 700 |
| Existing micro/defect coverage | 700 |
| New synthetic hard-boundary coverage | 1200 |
| New real-background boundary coverage | 700 |
| **Total** | **4000** |

## Held-Out Validation Package

| Role | Pairs |
|---|---:|
| New synthetic hard-boundary validation | 600 |
| New real-background boundary validation | 200 |
| **Total** | **800** |

The train and validation packages are disjoint.

## Verification

| Check | Result |
|---|---|
| R47 unit tests | 5 passed |
| Clean/convolved stage counts | matched for all four new stages |
| Train package source files | 4000 |
| Train package label files | 4000 |
| Validation package source files | 800 |
| Validation package label files | 800 |
| New-stage image size/dtype | 512 x 512, uint8 |
| Sampled src/lbl difference | nonzero for all four new stages |
| Clean preview | `r47_realistic_boundary_clean_preview.png` |
| Convolved preview | `r47_realistic_boundary_convolved_preview.png` |

Sample mean absolute source/label differences:

| Stage | Difference |
|---|---:|
| `stage_49_realistic_checkboard_corners` | 31.0117 |
| `stage_50_intersections_edges` | 9.6524 |
| `stage_51_real_background_boundaries` | 39.8528 |
| `stage_52_boundary_psf_stress` | 51.5056 |

## Next Step

Use `r47_realistic_boundary_train_4000` for the next Lab model training run,
then validate the trained checkpoints on the real `20250605_checkboard`
sequence with corner-geometry checks and external GMF packaging.
