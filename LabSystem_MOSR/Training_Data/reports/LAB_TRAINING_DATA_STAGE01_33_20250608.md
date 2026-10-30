# Lab Training Data Stage 01-33 - 2026-06-08

## Purpose

Build the first complete LabSystem training-data foundation from the existing
main-project recipe:

- Main geometry and ring data: stages 1-28.
- R40 microscopy feature data: stages 29-33.
- Formal input generation with the validated Lab BADS PSF.
- Gaussian-control inputs for PSF comparison only.
- R39 and R40 package materialization using Lab-generated data only.

R41, R42, and R44 research data are not included in this first formal lab
training-data foundation.

## Image Outputs

| Output set | Stage scope | Total images | Role |
|---|---:|---:|---|
| Clean GT | 1-33 | 2968 | Labels |
| Lab BADS PSF convolved | 1-33 | 2968 | Formal source inputs |
| Gaussian control convolved | 1-33 | 2968 | PSF comparison only |

The stage 1-28 clean GT comes from `Training_Data/Data_Simulaion.py`.
The stage 29-33 clean GT comes from the copied R40 data builder.

## Ring Replay Package

`tra_src_ring/` and `tra_lbl_ring/` were rebuilt from Lab-generated data only.

| Package | Pairs |
|---|---:|
| `tra_src_ring` / `tra_lbl_ring` | 1100 |

Selection source:

- Annulus and curve stages 8-10 and 13-22.
- Deterministic first 1100 pairs.

Manifest:

`Training_Data/tra_ring_manifest.json`

## R39 Packages

| Package | Pairs | Role |
|---|---:|---|
| `r39_shape_mix_safe` | 1240 | Conservative shape training package |
| `r39_shape_mix_strong` | 1590 | Strong shape training package |
| `shape_val_unseen` | 210 | Held-out shape validation |

## R40 Packages

| Package | Pairs | Role |
|---|---:|---|
| `r40_micro_capacity_train` | 1300 | Microscopy feature training package |
| `micro_val_unseen` | 100 | Held-out microscopy validation |

The R40 train/validation split was checked as disjoint before materialization.

## Preview

`Training_Data/reports/lab_training_data_stage01_33_preview.png`

## Verification

Fresh verification completed on 2026-06-08:

- Stage 1-33 clean GT counts match expected counts.
- Stage 1-33 Lab BADS PSF convolved counts match clean GT counts.
- Stage 1-33 Gaussian-control counts match clean GT counts.
- Ring replay has 1100 paired source/label images.
- R39 package manifests report 1240, 1590, and 210 pairs.
- R40 package manifests report 1300 and 100 pairs.
- R40 train/validation split is disjoint.
- The Lab ring packaging tests pass.
- No long-running Python process remained after generation.

## Next Step

Use this dataset foundation to prepare the first LabSystem training launch:

1. Train or fine-tune the COMBO-like lab baseline on the Lab BADS PSF data.
2. Reproduce the R39 shape and R40 microscopy feature lines on Lab data.
3. Compare against Gaussian-control data only as a PSF sanity check, not as the
   formal training source.
