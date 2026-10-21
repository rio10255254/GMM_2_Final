# R63 Pre-registered Protocol

## 1. Question

Which MOSR innovations causally improve boundary localization and displacement stability when the optical prior, starting weights, data split, training budget, and evaluation population are held fixed?

## 2. Scope

The PSF pathway is fixed in every condition and is outside the ablation scope. This round tests the measurement-oriented constraints and position-preserving reconstruction mechanisms only.

## 3. Training comparisons

### 3.1 Geometry x motion factorial

The primary factorial contains four conditions:

- Full: geometry anchor on, motion consistency on.
- No geometry: explicit boundary, centerline, distance, and boundary-position supervision off; motion consistency remains on.
- No motion: paired-sequence and motion-consistency supervision off; static geometry remains on.
- Neither: both groups off.

The factorial effects are computed as matched removal penalties, not by comparing each candidate only with Raw images. All confirmatory metrics are lower-is-better, so a positive value means that removing the mechanism made the result worse:

- Geometry main effect: average of `(No geometry - Full)` and `(Neither - No motion)`.
- Motion main effect: average of `(No motion - Full)` and `(Neither - No geometry)`.
- Interaction: `Neither - No geometry - No motion + Full`.

### 3.2 Upsampling comparison

Both candidates use the full loss recipe and additionally train the three decoder convolution layers. The only forward-path difference is whether the fixed anti-aliasing blur is applied after bilinear interpolation.

### 3.3 Component-resolution comparisons

Seven additional single-removal conditions resolve the broad factorial groups without changing the control, split, optics, trainable output modules, or training budget:

- Shape geometry: remove the boundary-mask, centerline, and distance-weighted edge terms.
- Global boundary position: remove only the all-sample boundary-position term.
- Identity-boundary guard: remove the low-bias boundary-band teacher and position protection.
- Boundary-region teacher: remove the general teacher constraint applied in a fixed band around the reference boundary.
- Adjacent-frame consistency: remove only the sequence-pair losses.
- Known-shift motion: remove only the motion-pair losses driven by known translations.
- Shift equivariance: remove the generic random-shift constraint that requires a shifted input to produce the correspondingly shifted boundary reconstruction.

Each component effect is defined as `single-removal minus Full` for a lower-is-better metric. These contrasts identify necessary contributions under the matched recipe; they are not assumed to sum exactly because the components can interact.

### 3.4 Matched output-module removals

Three additional conditions remove one output-stage mechanism for the entire
matched retraining and evaluation path:

- Boundary-residual adapter: remove the bounded local correction head.
- Raw-position anchor: remove the fixed low-frequency Raw-position preservation path.
- Quality gate: remove the image-dependent residual scaling path.

All shared trainable layers retain the same initialization and update budget.
The removed module is deliberately absent, so parameter-count differences are
reported as part of the architecture contrast. The boundary adapter is judged
primarily on threshold-robust CD error, the Raw-position anchor on real-sequence
step SD and within-grid disagreement, and the quality gate on within-grid
agreement plus cross-threshold CD-bound width. The same ringing, edge-width,
command-error, polarity, and validity guardrails apply.

### 3.5 Output-protection audit

Using one identical final checkpoint, evaluate:

- Full output path.
- Boundary adapter bypassed.
- Raw-detail anchor bypassed.
- Quality gate bypassed.
- All three bypassed.

These are inference-time diagnostics and are not treated as substitutes for retraining ablations.

## 4. Execution stages

The main, validation, and sequence batch sizes are fixed at 8, 2, and 2, respectively, matching the standalone full-training launcher. Four data-loader workers and the package-local fixed split are used in every condition. The primary suite retains the original full-training CUDA settings; two fixed seeds quantify run-to-run sensitivity. Strict deterministic execution is reserved for a forensic rerun if a matched contrast is too small to distinguish from runtime variation.

1. Smoke test: every training condition, one epoch, at most two batches.
2. Screening: every condition with seed `1261200` under one matched budget.
3. Confirmation: repeat all causal contrasts with seed `1261217` under the same budget.
4. Only checkpoints selected by the frozen internal rule are sent to external evaluation.

The matched retraining budget is 40 epochs with 32 main batches per epoch. This preserves the model's multi-stage 40-epoch schedule while limiting the number of parameter updates. It is a controlled local fine-tuning ablation, not a substitute for thirteen full-network 120-epoch retrainings from mechanism-naive initialization. Screening results may decide whether a longer confirmation is necessary, but may not change the metric definitions or evaluation population.

Budget escalation is global rather than candidate-specific. If at least three of the six seed-`1261200` screening conditions select their best internal checkpoint in epochs 36-40, all sixteen conditions and both seeds are continued from epoch 40 to epoch 60 with the same optimizer state. Otherwise the frozen 40-epoch budget is retained. This rule is evaluated before reconstruction metrics are inspected.

## 5. Evaluation populations

### 5.1 Real displacement

- Sequences: `50x_x_0p5um`, `50x_x_1um`, `20x_0p5um`, and `20x_1um`.
- Primary population: exactly 30 adjacent steps per sequence, selected once using Raw measurements only.
- Ranking: two-dimensional Raw local-motion deviation.
- Candidate outputs never affect inclusion or ranking.
- Sensitivity population: all steps with complete paired measurements for every compared method.

Because these capture families are represented in the standalone training package, this population supports controlled same-domain mechanism attribution, not an unseen-sample generalization claim.

### 5.2 Static SEM-referenced structure

- The same correctly oriented center-nine pillar grids at 20x and 50x are used for every candidate.
- SEM values are treated as reference geometry.
- Radius values are doubled before diameter comparison.
- The same center coordinates, profile directions, physical pixel sizes, and display range are locked across methods.

### 5.3 Synthetic translation

- Magnitudes: `0.08`, `0.4`, `0.8`, `2.0`, and `8.0` pixels where valid.
- Directions: eight directions at 45-degree intervals from 0 to 315 degrees.
- Border handling and valid masks are identical for all methods.

### 5.4 Optional external check

- If the original external GMF source images are restored, append the locked `0.08`, `0.8`, and `8` pixel analysis without changing any decision rule.
- Until those original source images are available, do not treat earlier reconstructed outputs as Raw inputs and do not include this optional check in the confirmatory verdict.
- The available package-manifest-unseen 50x image instead supplies the predeclared synthetic translation check, including 720-angle edge and ringing measurements.

## 6. Metrics

The confirmatory endpoints are fixed as follows. Geometry anchoring and the boundary-residual adapter are judged first on threshold-robust CD error in the package-manifest-unseen 50x SEM-linked image; 20x CD is supporting same-domain evidence. Relative-motion consistency and the Raw-position anchor are judged on step standard deviation and nine-pillar within-grid disagreement in the combined `all_sequences` population, with `50x_all` and `20x_all` used as direction checks; nominal-command MAE is supporting because the command is not independent stage truth. The quality gate must improve both combined step/grid stability and cross-threshold CD-bound direction at both magnifications without worsening the edge and ringing guardrails. Shift-safe upsampling is judged on synthetic vector error in the combined `primary_subpixel` population (0.08, 0.4, and 0.8 pixels), with edge-radius change and ringing as guardrails. Output-protection bypasses remain diagnostic and cannot independently establish a training-time causal claim.

### 6.1 Primary boundary metrics

- Threshold-robust median absolute CD error across the locked 35-65% bounds and both profile modes.
- Median 10-90% edge-transition width in nanometres.
- Per-pillar CD bound width and maximum absolute CD error.

### 6.2 Primary displacement metrics

- Step standard deviation in nanometres.
- Mean absolute deviation from the nominal command in nanometres.
- Mean nine-pillar within-grid disagreement in nanometres.
- Synthetic translation equivariance error in pixels.
- Synthetic 95th-percentile vector error and eight-direction error spread in pixels.

For combined displacement strata, step standard deviation is computed after
subtracting each sequence's own mean absolute step. This prevents the intended
0.5-versus-1.0 um command difference from being counted as instability. The
per-sequence values are unchanged by this centering. Nominal-command accuracy
is retained as the separate mean-absolute-deviation endpoint.

### 6.3 Guardrails

- Overshoot and undershoot around the pillar boundary.
- Ringing energy outside the first edge transition.
- Shift-induced ringing change on the known-translation cases.
- High-frequency excess relative to the matched Raw frame.
- Invalid or missing boundary crossings.
- Contrast-polarity preservation.

### 6.4 Fixed visual example

Any image or profile illustration uses center-nine position 5 (SEM pillar P29), seed `1261200`, and the same physical crop for every compared method. Grayscale limits are derived once from the matched Raw crop and reused without per-method contrast stretching. These illustrations explain the numerical result and are never used to select a checkpoint or establish a claim.

## 7. Statistical summaries

- Paired bootstrap confidence intervals are computed within each capture sequence and pillar identity.
- Combined displacement populations are resampled within each sequence, so every bootstrap replicate preserves the locked 30-step contribution of each sequence.
- The unit of replication is a step, pillar, or independently generated shift case, never an image pixel.
- Seed results are reported separately and then summarized; seeds are not pooled as if they were independent images.
- The broad geometry-motion factorial and matched upsampling pair are the primary causal contrasts. Single-component and output-module removals resolve mechanism roles, but no family-wise multiplicity correction is applied; their conclusions are therefore phrased more narrowly even when they pass the same effect, interval, and cross-seed rules.

## 8. Decision rules

A mechanism is described as supported only when all conditions hold:

1. The matched effect has the expected direction in both fixed-seed runs.
2. It improves at least one primary target metric by 10% or more.
3. The direction is consistent at both 20x and 50x, unless a magnification-specific explanation was predeclared.
4. Its paired 95% bootstrap interval excludes zero in the aggregate primary population.
5. No primary guardrail worsens by more than 15%, and no new polarity or boundary-validity failure appears.

Effects below 5% are treated as practically negligible. Effects between 5% and 10%, or effects that depend on only one seed or magnification, are reported as suggestive rather than confirmed.

## 9. Claim limits

- The experiment can attribute changes to the tested mechanism under the matched training recipe.
- Every condition begins from the same pre-trained checkpoint and gives every shared output-facing parameter the same update budget. Output-module removals deliberately omit only the named module. The experiment therefore estimates the marginal contribution of retaining each mechanism during the controlled fine-tuning stage; it does not prove that the mechanism is necessary when an entire network is trained from a mechanism-naive random initialization.
- It cannot prove that a module is universally optimal across all samples or optical systems.
- Bootstrap intervals quantify paired evaluation-unit uncertainty conditional on the two fixed-seed runs; two seeds do not characterize the full distribution of training variability.
- Visual sharpness alone is not a success criterion.
- No conclusion is written into the thesis until the full data-quality and reproducibility checks pass.
