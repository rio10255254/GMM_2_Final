# One-Shot v17 Target Prompt After v16 Validation

Use this whole file as the instruction for the next long-running experiment after v16.

## Mission

Design, train, and validate a v17 MOSR reconstruction candidate that fixes the exact v16 failures without using posthoc correction, per-sample calibration, or PSF-specific luck.

v16 is not promotable, but it gave a useful diagnosis:

- boundary overall mean improved;
- bright, annulus, and ellipse failures improved versus v14;
- 0.0 px and 0.5 px small-bias groups still failed versus R39;
- 20260603 real-motion tail stability was still worse than raw input and slightly worse than v14;
- Step selected-motion stability was slightly worse than R39 and v14.

Do not restart broadly. Make a targeted v17.

## Non-Negotiable Rules

- No per-sample posthoc calibration.
- No output shifting, drawing, or measurement correction after inference.
- Primary validation must be PSF-off or weak-PSF-off.
- Keep useful old data.
- Keep v14 and v16 as comparison baselines.
- Do not claim success unless simulated boundary, 20260603 motion, and Step motion all support it.

## Starting Evidence

Read first:

`LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/V16_VALIDATION_RESULTS.md`

v16 best checkpoint:

`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020/weights/best_tradeoff.pth.tar`

v14 best checkpoint:

`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217/weights/best_tradeoff.pth.tar`

R39 strong boundary reference:

Use the same R39 a970 reference used by v14/v16.

## v17 Training Design

Target only the diagnosed gaps:

- 0.0 px and 0.5 px small-bias boundary invariance.
- Motion stability that does not worsen 20260603 raw-tail stability.
- Step selected-motion stability that does not worsen R39 or v14.

Recommended design direction:

- Start from v16 if preserving its boundary gains is useful.
- Keep v14 as a motion-stability reference because v16 was slightly worse than v14 on 20260603 and Step.
- Add a targeted small-bias synthetic stage for 0.0 px and 0.5 px cases.
- Add a motion-protection guard that penalizes changes that increase tail/std-like instability, not just mean reconstruction loss.
- Avoid stronger generic sharpening pressure unless it is proven to help the gates.

## Required Validation

Run all three layers exactly as v16:

1. Matched 96-case diverse phantom boundary validation.
2. 20260603 real-sequence reconstruction and local motion summary.
3. Step selected 1 um center2048 reconstruction and motion summary.

Then run the triple gate.

## Acceptance Criteria

v17 is positive only if:

- boundary gate versus R39 has no small-bias failure;
- overall boundary mean is not worse than v16;
- 20260603 tail std dy beats v16 and v14, and is not worse than raw input;
- Step step std dx beats or matches R39 and v14;
- replicate 0 and replicate 1 do not disagree in a way that hides failure;
- validation is PSF-off or weak-PSF-off.

v17 is negative if it only improves visual sharpness or boundary mean while failing motion stability.

## Required Outputs

- Training run directory.
- Best checkpoint path.
- Training log.
- Dataset manifest.
- Matched diverse phantom validation folder.
- Gate versus R39 and R8.
- 20260603 reconstruction case and motion summary.
- Step reconstruction case and motion summary.
- Triple gate summary.
- Preview image comparing raw, R39/v14, v16, and v17.
- Plain progress note saying positive, negative, or inconclusive.
- Process cleanup check.

