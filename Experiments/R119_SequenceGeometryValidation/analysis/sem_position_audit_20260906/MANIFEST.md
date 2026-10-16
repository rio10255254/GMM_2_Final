# R119 cross-exposure position diagnosis

Canonical report: ../../reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md

This is a bounded extension of the corrected R119 analysis, not a new training round.
The study uses fixed E42, all exposures 13-24 and all 36 SEM-mapped pillars.
The 144-scene consumed confirmation set is not evaluated.

## Completion evidence

- 48 full-resolution images; 1,728 primary measurements; no missing observations.
- 864 Raw/base masks and historical contour metrics exactly reproduced.
- Independent Python boundary/area recomputation agrees with MATLAB.
- Corrected full MATLAB replay completed successfully, with all 1,728 scientific rows and all cell/mask arrays identical to the initial run. See replay_verification.json.
- All 88 protected input files match the original input_snapshot.json. Old receipts and handoff expectations were never changed.
- Figures were inspected: cross_exposure_results.png, all_exposure_images.png, review_examples.png.

## Preserved failure

The initial measure_sem.m compared original-intensity crops to the historical contrast-normalized display exports and failed its final cell-export assertion. Its program, measurements and log are retained. audit_cells.m independently reproduces the known historical mat2gray export and original-intensity crops on all 864 cases. measure_sem_replay.m fixes only that comparison, saves new outputs, and exits successfully. No contour result or expected historical artifact was changed to resolve the failure.

## Scientific limits

The position-off effect is consistent across these twelve exposures of one sample: 431/432 observations and all 36 pillar medians improve full E42. Yet 282/432 remain worse than Raw. Exact additive detail is kept but final texture is not identical or certified faithful; modified-output displacement is untested. No model promotion or further training follows automatically.

## Historical project context

project_context_before preserves the three root summaries before additions. New entries in PROJECT_STATE.md, ESTIMATOR_POLICY.json and Experiments/INDEX.md only add this diagnosis; previous claims and model roles are preserved.

output_inventory.json records the new artifacts for traceability, not as a substitute for behavioral verification or scientific judgment.
