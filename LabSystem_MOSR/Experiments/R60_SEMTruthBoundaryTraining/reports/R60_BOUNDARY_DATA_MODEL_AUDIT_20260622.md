# R60 Boundary Data / Model Audit - 2026-06-22

## Question

Why did the boundary reconstruction stay inaccurate even after R57/R58 fine-tuning?

## Verified Causes

1. R58 trained on partial targets, not SEM truth.
   - `r58_frac050` labels only moved halfway from the measured optical radius to SEM.
   - Example target bias: pillar `+5.52 nm`, via `-33.07 nm`.
   - Therefore the model was explicitly trained to stop short of the true SEM boundary.

2. R58 used synthetic anchors only.
   - `r58_frac050_train`: `base_pairs=0`, `anchor_pairs=512`.
   - The model mostly saw idealized circular sources, not real 100MG microscope crops.

3. R59 was post-hoc same-sample correction.
   - It measured the same image, estimated class shifts, then warped boundaries.
   - This can reduce a number but does not prove the model learned boundary placement.

4. The model output is only one grayscale image.
   - There is no direct CD/radius/boundary head.
   - Boundary correctness depends on indirect image losses and sidecar edge maps.

5. The internal checkpoint selector is not a CD selector.
   - R58 full training improved boundary-related validation terms through epoch 30, but `best_tradeoff` stayed near the early epochs.
   - R60 repeat12 pilot also showed validation loss improving while internal `best_tradeoff` could stay behind.

6. The first R60 real-crop data revision still had two data problems.
   - Real crops were underweighted: 71 real crops vs 1024 anchors.
   - Real-crop labels initially used hard-coded feature polarity; this inverted the label for this microscope image and made the model learn the wrong boundary direction.

## Repairs Added

- New experiment: `R60_SEMTruthBoundaryTraining`.
- New dataset builder:
  - real microscope crops from the 100MG image,
  - SEM-truth labels,
  - full local neighbor labels inside each crop,
  - source-matched label polarity,
  - real-crop repeat sampling for a balanced real/synthetic mix,
  - no R59-style same-sample correction fields.
- New launcher:
  - trains on both `stage_60_hs100mg_real_crop` and `stage_60_hs100mg_sem_anchor`,
  - disables PSF-forward loss for this uncalibrated sample,
  - marks CD validation as the adoption gate, not internal `best_tradeoff`.

## Current R60 Data Package

- Real unique crops: 71
- Real repeat: 12
- Real crop pairs: 852
- SEM anchor pairs: 1024
- Total pairs: 1876
- Target radius bias: 0.0 nm for both feature classes

## CD Validation Results

Absolute radius error vs SEM, in nm:

| Image / Model | Via | Pillar | Mean |
| --- | ---: | ---: | ---: |
| Original image | 66.13 | 11.04 | 38.59 |
| R55 PSF off | 80.28 | 43.41 | 61.84 |
| R55 PSF on | 81.59 | 46.55 | 64.07 |
| R60 initial SEM-truth pilot, low real-crop weight | 86.39 | 45.88 | 66.14 |
| R60 repeat12 before polarity fix | 198.03 | 158.94 | 178.49 |
| R60 repeat12 with polarity fix, latest epoch 4 | 30.09 | 7.75 | 18.92 |

## Readout

The boundary problem was not that the MOSR model family is useless. The dominant failure was that the training data did not consistently represent the true boundary:

- R58 intentionally used fractional SEM targets.
- R58 did not train on real 100MG crops.
- The first R60 repair exposed that polarity matters strongly for this sample.

After correcting target truth, real-crop weighting, and source-matched polarity, the R60 pilot beats the original image on both CD classes. This is still a pilot, not a final full-power model, but it validates the repair direction.

## Current Best Artifact

- Training run: `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r60_semtruth_realcrop_anchor_pilot_e004_mtb064_repeat12_polarityfix_20260622_20260622_005055`
- Reconstruction: `r60_semtruth_pilot_e004_mtb064_repeat12_polarityfix_20260622_latest_psf_off`
- Measurement report: `reports/measurements/r60_semtruth_polarityfix_e004_latest`
