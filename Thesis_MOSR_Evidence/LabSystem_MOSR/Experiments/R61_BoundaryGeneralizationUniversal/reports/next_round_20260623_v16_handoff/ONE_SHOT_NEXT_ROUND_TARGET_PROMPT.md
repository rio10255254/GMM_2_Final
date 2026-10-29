# One-Shot Target Prompt For The Next Long Run

Use this whole file as the instruction for the next agent or next resumed run.

## Mission

Continue the MOSR boundary-generalization experiment from the current R61 state. Build, train, and validate a new candidate model that improves boundary reconstruction without using per-sample posthoc calibration and without depending on one specific PSF setting.

The goal is not just to make images look sharper. The goal is to make reconstructed boundaries reliable enough that displacement measurement is also stable.

## Non-Negotiable Rules

- Do not use after-the-fact sample-specific correction.
- Do not "fix" measurements by drawing, shifting, or calibrating outputs after inference.
- Do not promote a candidate only because it works on the current sample.
- Do not make PSF-on the main result. Primary validation must be PSF-off or weak-PSF-off.
- Do not discard the useful old training data.
- Do not call a candidate successful unless simulated boundary, 20260603 real motion, and Step small-displacement checks all support it.

## Current Best Starting Point

Use v14 as the immediate predecessor and R39 a970 as the strong boundary reference.

v14 best checkpoint:

`Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217/weights/best_tradeoff.pth.tar`

v14 is useful but not enough:

- Simulated boundary mean: v14 0.483153 px, R39 0.483705 px.
- v14 still fails five strict boundary groups versus R39: bright polarity, 0 px bias, 0.5 px bias, annulus, ellipse.
- 20260603 tail std dy: raw 0.268818 px, R39 0.278475 px, v14 0.276390 px.
- Step center crop: R39 step std dx 0.097845 px, v14 0.097870 px.
- v14 triple gate result: fail.

## Training Design

Keep the successful backbone:

- Legacy shape data.
- SEM truth anchors.
- Universal synthetic shape data.
- Sequence guard data.
- R39 a970 prior.
- v14 camera-texture known-motion training data.

Add targeted pressure only where v14 fails:

- Bright boundaries.
- 0 px and 0.5 px small-bias cases.
- Annulus boundaries.
- Ellipse boundaries.
- Step-like displacement consistency.
- Repeat-capture stability.

Prefer synthetic and procedurally generated Step-like guards first. If the real Step data is ever used for training, split it by position or replicate stream and keep a true holdout. The safer first route is to use real Step as validation only, not as answer leakage.

## Required Validation Layer A - Simulated Diverse Phantom

Purpose: prove the candidate is not only memorizing the current sample.

Use the existing 96-case diverse phantom validation flow and compare against R39 a970 and R8.

Required checks:

- Overall mean chamfer must not be worse than v14.
- Bright-boundary mean must not regress versus R39.
- 0 px and 0.5 px small-bias groups must not regress versus R39.
- Annulus and ellipse groups must not regress versus R39.
- Report group failures, not just the overall mean.

Current v14 boundary validation folder:

`R61_motiontexture_dpv96_20260623/diverse_phantom_validation_20260623_164241`

## Required Validation Layer B - 20260603 Real Sequence

Purpose: test whether the model helps real displacement stability.

Reconstruct all 11 frames. Compare raw input, existing internal references, R39, v14, and the new candidate.

Use the tail statistic that removes the first warm-up interval.

Required checks:

- New candidate tail std dy must not be worse than raw input.
- New candidate tail std dy must beat v14 before claiming progress.
- Motion response must not collapse relative to v14.
- If the candidate improves visual sharpness but worsens this motion check, treat the result as not solved.

Current v14 20260603 summary:

`Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_motiontexture_full_e8.json`

## Required Validation Layer C - Step Small-Displacement Sequence

Purpose: test whether the model preserves small displacement behavior on a different capture set.

Source images:

`Step`

Known source structure:

- 788 BMP files.
- Interpreted as 394 positions with 2 captures per position.
- User camera/objective calibration: 2.5 um camera pixel, 20x objective, so object-plane pixel size is 0.125 um/px.
- Expected user-calibrated movement: 0.1 um = 0.8 px, 1.0 um = 8.0 px.

Use the selected +10-position sequence:

`Step_analysis_20260623/selected_1um_positions.csv`

For non-tiled inference, use the center 2048 x 2048 staged input:

`Step_analysis_20260623/selected_1um_input_center2048/bmp`

Known staged count:

- Center-crop input: 80 BMP files.
- R39 center-crop reconstruction: 80 BMP files.
- v14 center-crop reconstruction: 80 BMP files.

Required checks:

- Check same-position repeatability.
- Check selected +10-position step stability.
- Check replicate stream 0 and replicate stream 1 separately.
- Compare raw, R39, v14, and the new candidate.
- Do not claim physical 1 um accuracy until the raw-versus-reconstruction Step scale mismatch is explained.

Current Step summary:

`Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_RAW_R39_V14_SUMMARY.md`

Current Step preview:

`Step_analysis_20260623/step_center2048_raw_r39_v14_preview.png`

## Candidate Acceptance

The candidate is positive only if all of these are true:

- It does not regress the strict simulated boundary groups.
- It improves or protects the 20260603 real-motion tail stability.
- It improves or protects Step repeatability and selected-step stability.
- It works under PSF-off or weak-PSF-off validation.
- It does not rely on any posthoc per-sample calibration.

The candidate is inconclusive if it improves one layer but hurts another.

The candidate is negative if it only makes the image look sharper while boundary or displacement checks get worse.

## Required Outputs

Every long run must produce:

- Training run directory.
- Best checkpoint path.
- Training log.
- Dataset package description.
- Simulated diverse phantom validation folder.
- Gate versus R39 and R8.
- 20260603 reconstruction folder and motion summary.
- Step reconstruction folder and motion summary.
- Triple-gate summary.
- One preview image comparing raw, R39 or v14, and the new candidate.
- Progress-note update explaining whether the candidate is positive, negative, or inconclusive.
- Process cleanup check proving no background Python, conda, or inference process was left running.

## First Actions For The Next Agent

1. Read this prompt.
2. Read `PREVIOUS_ROUND_ORGANIZED_FILES.md`.
3. Confirm the v14 checkpoint and Step staged inputs still exist.
4. Run the existing R61 test suite before changing training code.
5. Implement the next candidate as a model/data improvement, not a measurement correction.
6. Run the three validation layers.
7. Report plainly whether the new candidate can support the thesis claim.

