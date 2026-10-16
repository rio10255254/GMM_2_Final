# R63 Protocol Revision Log

## 2026-07-17 - Inference-only invalid-output handling after the primary analysis freeze

- The locked static-CD evaluator rejected the inference-only `no_anchor` and `no_all` outputs because their radial contrast was invalid.
- The evaluator, thresholds, primary retraining ablations, and claim rules were not changed.
- Those two static-CD cells are reported as invalid rather than forced into numerical aggregation; their synthetic-shift and displacement diagnostics remain available.
- This is a diagnostic presentation rule applied after observing a genuine output failure. It does not alter any matched-retraining result or full-versus-Raw result.
- The machine-readable record is `results/output_protection_protocol_deviation.json`.

## 2026-07-17 - All three subpixel magnitudes included in the primary architecture stratum

- The known-shift set contains 0.08, 0.4, 0.8, 2.0, and 8.0 pixel translations.
- The primary subpixel architecture check now includes 0.08, 0.4, and 0.8 pixels rather than only the two endpoints.
- This yields 27 pillar-by-magnitude units before paired resampling and avoids omitting the intermediate subpixel condition.
- The 2.0 and 8.0 pixel cases remain secondary range checks.
- This definition was frozen before any R63 candidate reconstruction metric was generated or inspected.

## 2026-07-17 - Matched output-module retraining contrasts added before reconstruction scoring

- The initial plan contained an inference-only bypass audit for the boundary adapter, Raw-position anchor, and quality gate.
- A bypass can show operational dependence but cannot compare against an alternative that was trained fairly without the module.
- Three full matched retraining conditions were therefore added, one per output module, for both seeds and the same global convergence rule.
- Shared parameters retain the same initialization, data, optics, and update budget; only the named output path is absent.
- The inference-only audit remains as complementary mechanism evidence and is not substituted for retraining.
- These conditions and their claim rules were frozen before any R63 candidate reconstruction metric was generated or inspected.

## 2026-07-17 - Combined displacement stability definition corrected before reconstruction scoring

- The four real sequences contain two commanded step sizes, 0.5 and 1.0 um.
- Directly pooling their absolute step magnitudes would make the intended command-size difference appear as instability.
- The combined 50x, 20x, and all-sequence stability endpoints now use within-sequence mean-centered step residuals; each individual sequence SD is mathematically unchanged.
- Nominal-command error remains a separate endpoint and is not removed by the centering.
- Combined-population bootstrap sampling is stratified by sequence and preserves 30 locked steps per sequence.
- This correction was made before any R63 candidate reconstruction metric was generated or inspected.

All entries below were made before any R63 candidate checkpoint was reconstructed on the static-CD, real-displacement, or synthetic-shift evaluation populations.

## 2026-07-17 01:02 Asia/Taipei

- Corrected the written factorial sign convention to match the predeclared lower-is-better removal penalty used by the analysis.
- Corrected the synthetic-shift description from four directions to the implemented eight directions at 45-degree intervals.
- Marked external GMF as optional because its original Raw source folders were unavailable; old reconstructions were explicitly prohibited from being relabeled as Raw inputs.

## 2026-07-17 01:07 Asia/Taipei

- Added five single-component removals before examining reconstruction metrics:
  - shape geometry;
  - global boundary position;
  - identity-boundary guard;
  - adjacent-frame consistency;
  - known-shift motion pairs.
- Expanded the matched suite from 6 to 11 conditions while retaining the same two seeds, split, starting checkpoint, optical settings, and budget.
- Kept the original six-condition screen as the frozen convergence-gate population; if triggered, the extension applies globally to all 11 conditions.

## 2026-07-17 01:17 Asia/Taipei

- Locked continuation runs to the source run's monitor reference so epochs 1-40 and 41-60 use comparable checkpoint-selection scores.
- Required final checkpoint selection to consider both the original and continuation run directories over the complete 1-60 budget.
- Added combined `all_sequences`, `50x_all`, `20x_all`, and `primary_subpixel` analysis strata before candidate reconstructions were measured.

## 2026-07-17 01:33 Asia/Taipei

- The full training log exposed a separate general boundary-region teacher that was not covered by the earlier low-bias identity guard.
- Added one single-removal condition for this teacher, bringing the final matched suite to 12 conditions and 24 runs.
- Kept the original six-condition convergence gate unchanged; its already-triggered global extension now applies to all 12 conditions.

## 2026-07-17 01:38 Asia/Taipei

- The full training trace exposed a generic random-shift equivariance loss that remained active in the earlier broad motion removal.
- Added a single-removal shift-equivariance condition and incorporated it into the broad motion-off definition.
- Marked the two already completed seed-`1261200` broad-motion runs for replacement; they remain in the audit trail but are excluded from checkpoint selection.
- The final matched suite contains 13 conditions and 26 valid runs; the triggered global extension applies to all 13 conditions.

No thesis text or conclusion was changed during these revisions.
