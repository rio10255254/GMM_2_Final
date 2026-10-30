# R62 Target-Boost Audit 20260705

## Completion Check

- R62 v2 pseudo-boundary data package was created and trained.
- R62 v2 was reconstructed on the 20260702 100MG and 20260704 20x/5x displacement sets.
- Raw / R61 / R62 v2 displacement comparison was generated.
- The v2 failure mode was traced instead of being treated as success.
- A v3 real-motion data package was created with real sequence motion pairs.
- R62 v3 real-motion training was run and checked against R61.

## Main Result

R62 v2 and R62 v3 did not produce a practically different reconstruction from R61 v16.

The strongest evidence is the image-level comparison:

- R62 v2 output differs from R61 by only 0 or 1 gray level in a very small number of pixels.
- Mean absolute image difference is near zero:
  - 20260702 x_1um: 0.000007 gray level
  - 20260704 20x_1um: 0.000003 gray level
  - 20260704 5x_0p5um: 0.000006 gray level

So the displacement table looking identical is not a measurement-method illusion. The actual reconstructed images are essentially the same.

## R62 v2 Training Finding

R62 v2 started from R61 v16 and used:

- 5,840 training pairs
- 1,500 target real pseudo-boundary patches
- R61 teacher edge-sharpened pseudo labels
- weak PSF disabled for reconstruction

The problem is that the pseudo labels were still highly tied to the R61 teacher. They sharpened contrast and edge steepness, but did not create a meaningfully different boundary-position target.

Weight comparison confirmed this:

- Changed parameters vs R61: about 0.059% of tensor elements
- Mean absolute weight change: about 4.7e-10
- Only boundary_adapter and weak_psf_block.beta_scale changed visibly
- Decoder and main U-Net layers stayed unchanged

## R62 v3 Real-Motion Attempt

To fix the v2 weakness, a new data package was created:

- Package: r62_target_sample_boost_v2_real_motion
- Total pairs: 7,040
- Added real-motion frames: 1,200
- Real-motion ROI sequences: 24
- Real-motion consecutive pairs: 1,176

The real-motion stage used the same format as the existing trainer expects:

- filenames include seq/frame ids
- each frame has a motion metadata JSON
- metadata stores dx/dy from the previous frame
- 20260704 uses commanded displacement converted from Basler 3.45 um pixel size and 20x/5x magnification
- 20260702 uses the stable internal phase result as the conservative dx target

The training launcher was also changed:

- candidate: r62_target_real_motion_v3
- trainable groups requested: boundary_adapter, p1, p2, p3, u1, u2, u3, out
- real-motion stage included in both training and motion loss
- motion pairs enabled: 1,600 pairs per epoch

Smoke training confirmed that the trainer really loaded the real-motion pairs.

Full v3 training ran:

- 5 epochs
- 800 train batches per epoch
- started from R61 v16 best weight
- best epoch selected: epoch 2

But weight comparison still showed almost no practical movement:

- Changed parameters vs R61: about 0.059%
- Mean absolute weight change: about 2.9e-10
- Main decoder layers still did not change
- Output is expected to remain visually equivalent to R61 under PSF-off inference

## Root Cause

The failure is not that the run crashed. The failure is that the model stayed locked to R61.

There are two confirmed causes:

1. The target pseudo labels are too teacher-like.
   They mostly preserve R61 boundary position, so the training target does not demand a new answer.

2. The fine-tuning setup is still too conservative.
   Even after adding real-motion pairs and requesting more trainable decoder layers, the saved checkpoint shows meaningful movement only in tiny adapter/weak-PSF parameters.

This means the current R62/R63-style fine-tuning cannot yet be claimed as a stronger model.

## Files Produced

- Dataset builder for v2 pseudo-boundary package:
  `LabSystem_MOSR/Experiments/R62_TargetSampleBoost/scripts/prepare_r62_target_sample_dataset.py`
- Dataset builder for v3 real-motion package:
  `LabSystem_MOSR/Experiments/R62_TargetSampleBoost/scripts/prepare_r62_target_motion_dataset.py`
- R62 launcher with v1/v2/v3 candidates:
  `LabSystem_MOSR/Experiments/R62_TargetSampleBoost/scripts/launch_r62.py`
- Reconstruction runner:
  `LabSystem_MOSR/Experiments/R62_TargetSampleBoost/scripts/run_r62_reconstruction_for_new_displacement_sets.py`
- Raw/R61/R62 v2 displacement analysis:
  `LabSystem_MOSR/Experiments/R62_TargetSampleBoost/scripts/analyze_r62_displacement_effect.py`
- R62 v2 displacement report:
  `LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v2_targetboost_displacement_eval/R62_TARGETBOOST_VALIDATION_READOUT.md`
- R62 v2 full training run:
  `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_real_pseudo_stepguard_v2_stronger_stronger_full5_20260705_20260705_205634`
- R62 v3 real-motion full training run:
  `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_real_motion_v3_realmotion_full5_20260705_20260705_213532`

## Recommended Next Move

Do not continue by only adding epochs.

The next useful change should be a controlled training-code or objective change that proves the model can actually move:

1. Add a gradient/update audit during the first 10 batches and record per-layer update size.
2. If decoder gradients are zero or near zero, fix that before training again.
3. Temporarily remove region-KD and identity guard for a short diagnostic run.
4. Train on a tiny real-motion overfit set and require visible output change.
5. Only after that, run a full target-boost training round.

Until that is done, R61 v16 remains the strongest verified thesis candidate for these displacement analyses.
