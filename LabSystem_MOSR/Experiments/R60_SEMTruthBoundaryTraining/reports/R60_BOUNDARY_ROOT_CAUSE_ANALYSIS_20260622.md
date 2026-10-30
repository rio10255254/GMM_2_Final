# R60 Boundary Root Cause Analysis - 2026-06-22

## Scope

This note isolates why the current MOSR reconstruction can look visually improved while the measured boundary/CD remains unstable.
The target sample is the 20260618 100MG Basler capture, compared against the SEM-derived CD reference.

## Completion Criteria For This Pass

- Verify the active R60 training package and the older R58 package.
- Compare original image, short R60 training, long R60 training, and internal best checkpoints against SEM CD.
- Check whether validation metrics and checkpoint selection agree with boundary/CD accuracy.
- Separate data-root causes from model/training-root causes.

## Evidence Summary

### 1. Older R58 data was not SEM-truth boundary supervision

The previous R58 full-power package contains 4096 synthetic anchor pairs and no real microscope crops.
Its target radius was still biased away from SEM truth:

| Package | Source pairs | Real microscope crops | Target bias, via | Target bias, pillar |
|---|---:|---:|---:|---:|
| R58 frac050 | 4096 synthetic anchors | 0 | -33.07 nm | +5.52 nm |
| R60 SEM-truth | 1024 anchors + 852 real-crop repeats | 71 unique crops | 0.00 nm | 0.00 nm |

Conclusion: old training could not learn true SEM boundaries because the target itself was not true SEM and the domain was synthetic-only.

### 2. Current R60 data fixes radius truth, but still has domain and split weakness

The active R60 package has:

- 1876 total pairs.
- 1024 synthetic SEM anchors.
- 852 real-crop pairs, but only 71 unique real microscope crops repeated 12 times.
- Balanced feature counts overall: 944 via, 932 pillar.
- Target radius bias is exactly 0 nm for all pairs.

However, because real crops are duplicated before the train/validation split, a path-level random split leaks same-feature duplicates into validation.
With the current sorted-path split and seed, 45 of the 71 unique real-crop groups appear in both train and validation.

Conclusion: validation loss can look good even when the model is only learning duplicated local crops, not robust full-field boundary placement.

### 3. The model output does not directly represent boundary or radius

The current model produces one grayscale reconstructed image.
It does not output:

- boundary map,
- signed distance map,
- radius/CD estimate,
- shape class-aware geometry.

Boundary information enters only through indirect losses on grayscale image, gradients, edge orientation, and geometry sidecars.

Conclusion: the model can improve image/edge losses without preserving the exact radius.

### 4. Internal validation and best checkpoint selection are misaligned with CD

The validation loop measures reconstruction, gradient magnitude, edge orientation, PSNR, SSIM, and high-frequency proxies.
It does not measure CD against SEM.

The internal `best_tradeoff` checkpoint is therefore not a reliable adoption gate:

| Run | Checkpoint | Mean abs radius error | Via abs error | Pillar abs error |
|---|---|---:|---:|---:|
| Short R60 polarity-fixed | latest | 18.92 nm | 30.09 nm | 7.75 nm |
| Short R60 polarity-fixed | best_tradeoff | 62.33 nm | 82.33 nm | 42.33 nm |
| Fullish R60 | latest / epoch_012 | 43.12 nm | 31.41 nm | 54.83 nm |
| Fullish R60 | best_tradeoff | 65.77 nm | 86.10 nm | 45.43 nm |

Conclusion: the old internal selector can select a visually/GMF-preferred checkpoint that is bad for CD.

### 5. Longer training creates radius drift, especially for pillars

The same fullish training run was scanned at epoch checkpoints:

| Image/checkpoint | Mean abs radius error | Via abs error | Pillar abs error | Note |
|---|---:|---:|---:|---|
| Original image | 38.59 nm | 66.13 nm | 11.04 nm | Basler original |
| Short R60 e004 latest | 18.92 nm | 30.09 nm | 7.75 nm | Beats original for both classes |
| Fullish epoch_005 | 21.33 nm | 25.14 nm | 17.51 nm | Mean improves, pillar worsens vs original |
| Fullish epoch_010 | 37.30 nm | 27.29 nm | 47.32 nm | Pillar has drifted badly |
| Fullish epoch_012 | 43.12 nm | 31.41 nm | 54.83 nm | Final checkpoint is worse than original on mean |

Meanwhile the ordinary validation metrics improved from epoch 0 to epoch 12:

- validation total: 0.057573 -> 0.024068
- validation reconstruction: 0.006016 -> 0.002456
- validation SSIM: 0.9249 -> 0.9689

Conclusion: visual/reconstruction validation improves while CD degrades. This is the strongest evidence of metric-target mismatch.

### 6. Label polarity was a real failure mode

Before source-matched polarity was fixed, the repeated-real-crop R60 run produced very large CD error:

- mean abs radius error: 178.49 nm
- via: 198.03 nm
- pillar: 158.94 nm

After fixing source-matched polarity, the short e004 run reached:

- mean abs radius error: 18.92 nm
- via: 30.09 nm
- pillar: 7.75 nm

Conclusion: boundary labels are highly sensitive to local microscope contrast polarity. This is fixed in the active R60 package, but it explains why earlier attempts collapsed.

## Root Cause Chain

The boundary inaccuracy is not caused by a single bad switch.
The verified chain is:

1. Older training data did not encode true SEM boundaries.
2. Current data improves truth labels, but has too few unique real microscope crops and duplicate leakage in validation.
3. The model only outputs grayscale images, so exact boundary/radius is an indirect consequence, not a direct prediction target.
4. The training loss and validation metrics reward image similarity and edge appearance more than signed boundary position.
5. Long training keeps improving those proxy metrics, but drifts the pillar radius outward.
6. The internal best-checkpoint rule does not know about CD and can pick a bad checkpoint.

## What This Means

The system is not useless: the short polarity-fixed R60 model proves the network can move boundaries closer to SEM on this sample.
But the current training design is not stable enough to trust "longer training" or "best_tradeoff" as boundary-accurate.

The immediate failure is over-optimization of proxy image metrics without a hard SEM/CD boundary gate.
The deeper model limitation is that boundary geometry is indirect instead of explicitly predicted or directly constrained.

## Corrective Direction

Next fixes should target the training/data system, not post-hoc per-sample calibration:

1. Use group-aware train/validation split so repeated real crops never leak across train and validation.
2. Promote external CD-vs-SEM validation to the checkpoint selector.
3. Keep early stopping around the CD-best point instead of pushing training to a fixed longer epoch count.
4. Add more unique real microscope crops or reduce synthetic-anchor dominance.
5. Add a direct boundary/radius supervision path, such as an auxiliary boundary/signed-distance/radius head or a differentiable shape-aware boundary loss.
6. Reduce late-stage edge/geometry terms if they continue to expand pillars after epoch 5.

## Update After Split Repair

After this analysis, the R60 launcher/trainer was changed to use a manifest-grouped fixed split.
All repeats of the same real crop now stay on only one side of train/validation.
The split was also stratified by source group and feature so validation contains real crop + synthetic anchor, via + pillar.

Verified real-data split:

| Split | Train pairs | Validation pairs | Group overlap | Validation strata |
|---|---:|---:|---:|---|
| grouped_seed1337_val100 | 1676 | 200 | 0 | real/pillar, real/via, anchor/pillar, anchor/via |
| grouped_seed1337_val020 | 1824 | 52 | 0 | real/pillar, real/via, anchor/pillar, anchor/via |

The clean stratified short run no longer reproduces the earlier best-looking result:

| Run | Mean abs radius error | Via abs error | Pillar abs error | Passes original per-class gate |
|---|---:|---:|---:|---|
| Original image | 38.59 nm | 66.13 nm | 11.04 nm | reference |
| Earlier short R60 before split repair | 18.92 nm | 30.09 nm | 7.75 nm | yes |
| Grouped split short R60, e004 mtb064 | 21.71 nm | 30.90 nm | 12.53 nm | no |
| Grouped + stratified split short R60, e004 mtb064 | 26.54 nm | 39.59 nm | 13.48 nm | no |

This confirms the previous optimistic result was not robust under a clean validation design.
The model still improves the large via error, but pillar remains slightly worse than the original image.

The source bias that the model must learn is asymmetric:

| Source group | Feature | Mean source radius bias | Mean source bias in pixels |
|---|---|---:|---:|
| real crop | via | -65.38 nm | -0.948 px |
| real crop | pillar | +9.49 nm | +0.138 px |
| synthetic anchor | via | -66.13 nm | -0.958 px |
| synthetic anchor | pillar | +11.04 nm | +0.160 px |

The via correction is almost one pixel, so the image-to-SEM boundary shift is learnable even with current losses.
The pillar correction is only about 0.14-0.16 px, so ordinary grayscale/edge losses can easily ignore or wash out that shift.
This is now the leading model/training root cause: the current single-image-output model is being asked to learn a subpixel, class-dependent radius correction indirectly.
