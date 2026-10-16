# Next Round Target Prompt - v15 Step Guard

Use this as the starting instruction for the next long-running experiment.

## Mission

Train and validate the next MOSR reconstruction candidate without discarding old training data, without per-sample post-processing calibration, and without relying on one specific PSF calibration. The goal is to improve boundary reconstruction and displacement measurement at the same time across multiple datasets.

## Current State

- R39 a970 is the current strong boundary baseline.
- v14 motion-texture training improved the simulated boundary mean and gave the best R61-series 20260603 local-motion tail stability so far.
- v14 still failed the strict boundary group gate and still did not beat raw input on the 20260603 real-motion probe.
- Step has 788 BMP images, interpreted as 394 positions with two captures per position.
- User-provided Step calibration: camera pixel 2.5 um, objective 20x, object-plane pixel size 0.125 um/px.
- Expected user-calibrated motion: 0.1 um = 0.8 px, 1.0 um = 8.0 px.
- Raw Step probe result: same-position repeat median motion is about 0.019 px; selected position +10 pairs measure about 0.73-0.74 px, far below the 8 px expectation.
- A center 2048 x 2048 crop of the selected Step frames has been staged for practical GPU inference. It preserves the raw ROI motion probe numbers from the full 5120 x 5120 images.
- Full-size 5120 x 5120 R39 Step inference was attempted and failed on every frame with CUDA out-of-memory. Do not rerun full-size Step inference unless tiled inference or a smaller crop is implemented.
- Center-crop R39 a970 Step inference completed for 80/80 selected frames with PSF-off settings. Its Step probe measured repeat median motion about 0.134 px and selected +10 median motion about 8.026 px.
- Center-crop v14 Step inference completed for 80/80 selected frames with PSF-off settings after switching to direct unbuffered inference. Its Step probe measured repeat median motion about 0.134 px and selected +10 median motion about 8.027 px.
- The current raw/R39/v14 center-crop Step comparison table is saved at `D:\GMM_2_Final\Step_analysis_20260623\STEP_MOTION_PROBE_CENTER2048_RAW_R39_V14_SUMMARY.md`.
- v14 triple gate is now recorded at `D:\GMM_2_Final\Step_analysis_20260623\triple_gate_v14_boundary_real_step_vs_raw_r39.json`: it fails boundary, 20260603 real motion, and Step stability versus R39 by a very small Step margin.

## Mandatory Datasets

1. Simulated diverse phantom boundary validation
   - Purpose: prove the model is not only memorizing the current sample.
   - Must compare against R39 a970 and R8.
   - Must inspect group failures, not only overall mean.

2. 20260603 real sequence
   - Purpose: test whether reconstruction improves real displacement stability.
   - Must compare raw input, reg300/COMBO-like internal case, R39 a970, v14, and the new candidate.
   - Tail statistic must still remove the first warm-up interval.

3. Step small-displacement sequence
   - Source: `D:\GMM_2_Final\Step`
   - Use the selected 1 um manifest from `D:\GMM_2_Final\Step_analysis_20260623\selected_1um_positions.csv`.
   - For current non-tiled GPU inference, use the staged center-crop input folder:
     `D:\GMM_2_Final\Step_analysis_20260623\selected_1um_input_center2048\bmp`
   - Use positions `0, 10, 20, ..., 390`.
   - Use both replicate streams:
     - replicate 0: image indices `0, 20, 40, ..., 780`
     - replicate 1: image indices `1, 21, 41, ..., 781`
   - Same-position pair check must be treated as repeatability baseline.
   - The Step pixel-scale mismatch must be treated as an open calibration issue; do not claim physical 1 um = 8 px until resolved.

## PSF Policy

- Primary validation must use PSF-off or weak-PSF-off inference so the candidate is judged mostly by the model itself.
- PSF-on may be run only as an ablation.
- Do not promote a candidate because one PSF setting happens to make one dataset look better.
- If a PSF-on result differs strongly from PSF-off, report it as optical-system sensitivity, not as model generalization.

## Training Strategy

Keep the successful old-data backbone:

- Legacy shape anchors.
- SEM truth anchors.
- Universal synthetic shape data.
- Sequence guard data.
- R39 a970 prior weights.
- v14 camera-texture known-motion data.

Add targeted pressure only where v14 still fails:

- Bright boundaries.
- 0.0 px and 0.5 px small-bias guards.
- Annulus boundaries.
- Ellipse boundaries.
- Step-like small displacement and repeat-capture stability.

Do not use a same-sample after-the-fact correction. If Step is used for training, split it by position so at least one replicate stream or a block of positions remains held out for validation. Prefer using Step first as a validation guard before using it as training data.

## Candidate Acceptance Gates

A new candidate is not successful unless all required gates are checked.

### Gate A - Simulated Boundary

- Overall mean chamfer must not be worse than v14.
- Bright boundaries must not regress versus R39 a970.
- 0.0 px and 0.5 px bias groups must not regress versus R39 a970.
- Annulus and ellipse groups must not regress versus R39 a970.
- Any improvement that only helps dark or large-bias cases while hurting small-bias cases is not acceptable.

### Gate B - 20260603 Real Motion

- Reconstruct all 11 frames.
- Tail std dy must not be worse than raw input.
- Tail std dy must beat v14 before claiming progress.
- Response must not collapse relative to v14.

### Gate C - Step Small Displacement

- Confirm 788 BMP files and two captures per position before testing.
- Confirm same-position repeatability remains low on raw and reconstruction.
- Build the 1 um sequence from positions +10 using the saved manifest.
- Compare raw, R39 a970, v14, and the new candidate.
- Check both replicate streams.
- Do not claim physical accuracy until the Step scale mismatch is resolved.
- A candidate that improves simulated boundary but worsens Step repeatability or Step step stability is not acceptable.
- R39 center-crop Step should be treated as a strong but suspicious reference: it recovers about 8 px commanded-step motion while raw center-crop motion is about 0.74 px. Verify whether this is true scale recovery or reconstruction-induced scaling before using it as thesis evidence.

## Stop Conditions

Stop and rethink the design if any of these happen:

- Two consecutive candidates improve simulated boundary mean but worsen both 20260603 and Step motion.
- Step results are inconsistent between replicate 0 and replicate 1.
- The candidate passes only with PSF-on but fails PSF-off.
- The model improves visible sharpness but reduces the motion-probe response.

## Required Outputs

Each long run must produce:

- Training run directory.
- Best checkpoint path.
- Training log.
- Diverse phantom validation directory.
- Gate versus R39 and R8.
- 20260603 reconstruction case and motion summary.
- Step reconstruction case and motion summary.
- Dual or triple gate summary.
- One preview image comparing raw, R39/v14, and new candidate.
- Progress-note update explaining whether the candidate is positive, negative, or inconclusive.
- A short environment note if any inference process stalls before writing the first frame. Do not leave background Python, conda, or inference processes running.

## Reporting Rule

Report in plain language:

- What was trained.
- Which old data was kept.
- Which new guard was added.
- What improved.
- What still failed.
- Whether it is safe to use in the thesis claim.

Do not claim success unless the simulated boundary, 20260603 motion, and Step small-displacement checks all support it.
