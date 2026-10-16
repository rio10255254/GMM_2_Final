# R60 Full-Power R58/R59 Result

Generated: 2026-06-22 00:02 local time

## Scope

This run used the full-power R58 `r58_frac050` branch on the 20260618 100MG Basler sample, then applied the R59 CD-closed-loop boundary correction to the reconstructed image.

## Inputs

- Source sample image: `20260618_100MG/Image__2026-06-18__17-10-31.bmp`
- R58 full training package: `LabSystem_MOSR/Training_Data/r60_full_power/hs100mg_basler/r58_frac050_train`
- R58 full checkpoint: `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r58_frac050_full_e030_mtb512_20260621_2300_20260621_231035/weights/best_tradeoff.pth.tar`

## R58 Full Training Observation

- Training ran for 30 epochs with up to 512 batches per epoch.
- The best accepted reconstruction checkpoint stayed at epoch 2.
- Later epochs improved validation reconstruction metrics but were not accepted as best because the boundary guard kept flagging oversmoothing / boundary-band degradation.

## CD Results

All values are mean absolute radius error versus SEM, in nm.

| Image / method | Mean | Via | Pillar | Beats original |
|---|---:|---:|---:|---|
| Original camera image | 38.59 | 66.13 | 11.04 | baseline |
| R58 pilot frac050 e8 | 54.91 | 73.95 | 35.88 | no |
| R58 full frac050 e30 | 53.69 | 75.08 | 32.30 | no |
| R59 corrected R58 full, independent R57 measurement | 2.55 | 3.36 | 1.75 | yes |

## R59 Boundary Correction

Learned class-level radius shifts:

- Via: +1.0322 px
- Pillar: -0.4617 px

Corrected image:

`LabSystem_MOSR/Experiments/R59_CDClosedLoopBoundaryLayer/reports/r59_cd_closed_loop/r58_frac050_full_e030_mtb512_20260621_2300/r58_frac050_full_e030_mtb512_20260621_2300_r59_cd_closed_loop.bmp`

Independent R57 measurement folder:

`LabSystem_MOSR/Experiments/R59_CDClosedLoopBoundaryLayer/reports/r59_cd_closed_loop/r58_frac050_full_e030_mtb512_20260621_2300/independent_r57_measurement`

## Interpretation

The full R58 training alone did not solve the CD boundary bias. It slightly improved over the R58 pilot but remained worse than the original camera image for CD.

The R59 boundary layer strongly corrected the same-sample CD bias and passed the independent R57 re-measurement. This is strong same-sample calibrated evidence, not yet proof of cross-sample generalization.
