# R62 self-shift training decision, 2026-07-05

## Decision

Do not start full long training yet.

The earlier R62 no-AMP update proved that the model can really update, but short validation did not prove a stable improvement on the real displacement goal. The next full run would risk spending time on a model that sharpens boundaries while not improving, or even slightly hurting, small-step displacement stability.

## Root cause found

The original real-motion training stage contains unstable ROIs. Some target-sample crops have repeated structures, so phase matching on that crop can report almost no movement even though the sequence command says it moved. Examples from the ROI-quality check:

- 100MG x_1um roi00: target -14.608 px, measured median -0.083 px.
- 100MG x_1um roi03: target -14.608 px, measured median -0.391 px.
- 100MG x_0p5um roi01: target -7.248 px, measured median -0.043 px.
- 100MG x_0p5um roi02: target -7.248 px, measured median -0.260 px.

This matches the concern that repeated pillar structures can make the matching frame lock onto the wrong repeated feature.

Evidence table:

- `r62_noamp_candidate_displacement_eval_20260705/real_motion_roi_quality.csv`

## Data added

A new package was created:

- Package role: self-shift exact-motion target texture data.
- Meaning: it uses the user's real microscope images as texture, then creates an exact known subpixel shift from each patch.
- Purpose: keep the sample appearance real, but remove wrong motion labels caused by repeated-pattern matching.

New package:

- `Training_Data/r62_target_sample_boost/hs100mg_basler/r62_target_sample_boost_v3_selfshift_motion`

Counts:

- Total pairs: 7,760.
- Added self-shift frames: 720.
- Added exact-motion self-shift pairs: 360.
- Each of the six sequence groups contributes 60 exact-motion pairs.

## Candidate tests

### V4 self-shift candidate

Design:

- Uses the new self-shift package.
- Opens boundary adapter, p1, p2, and output layer.
- Uses self-shift data for motion loss.
- Keeps the original R61 model as teacher guard.

Short result:

- Training ran correctly with AMP off.
- Main trainable layers updated.
- But after 2 epochs x 200 batches, validation moved in the wrong direction:
  - Edge width changed from 6.9390 to 6.4797 after epoch 1.
  - Sequence score drifted from 0.5580 to 0.5570 by epoch 2.
  - Best checkpoint stayed at epoch 0, meaning training did not beat the starting R61 state.

Run folder:

- `Experiments/Training_Runs/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_motion_v4_v4_selfshift_short_e2_b200_20260705_20260705_225038`

### V5 adapter-guard candidate

Design:

- Uses the same self-shift package.
- Only allows the small boundary adapter to update.
- Increases R61 teacher guard.
- Reduces single-image boundary sharpening pressure.
- Makes motion loss stronger than V4.

Short result:

- Training ran correctly with AMP off.
- It avoided the edge-width collapse seen in V4.
- But it was too conservative: sequence score stayed essentially unchanged at 0.5580.
- It did not show enough improvement to justify long training.

Run folder:

- `Experiments/Training_Runs/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_adapterguard_v5_v5_adapterguard_short_e2_b200_20260705_20260705_225547`

## Verification done

- Unit tests for self-shift data creation: passed.
- Unit tests for V4/V5 launcher settings: passed.
- Dry-run for V4 and V5: passed.
- V4 short training: completed.
- V5 short training: completed.
- No full long training was launched.

## Next technical direction

The current motion consistency loss mostly teaches the network that output B should look like output A shifted by the known amount. A convolutional model can already satisfy much of that by being shift-consistent, so this does not strongly force better absolute boundary localization.

The next useful improvement should add a direct displacement-measurement loss, such as a differentiable edge-centroid or phase-like loss on the reconstructed outputs. That would train the model on the same kind of measurement the thesis cares about: "after reconstruction, the measured boundary displacement should equal the known step."
