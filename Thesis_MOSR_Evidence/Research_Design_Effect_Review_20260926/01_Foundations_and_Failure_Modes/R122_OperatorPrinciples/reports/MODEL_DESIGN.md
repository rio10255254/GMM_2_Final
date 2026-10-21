# A transparent, useful reconstruction model: design contract

Decision date: 2026-09-08. This is a design specification informed by executed diagnostics, not a trained model or a guarantee of universal recovery. Primary comparisons will be Raw, known simulated truth, and a simple explicit imaging fit. V42 is not a required target to beat.

## 1. Define the quantity before estimating it

Separate four coordinates: the physical material boundary; the ideal optical object/intensity boundary; the blurred sensor observation; and a chosen image readout (half contrast, steepest point, ACM contour). They need not coincide. An SEM-to-optical correspondence needs independently calibrated scale, registration, material/contrast meaning and uncertainty. It must not be fitted per test pillar to improve the candidate.

Image formation is recorded as `y = Q{ b + a * P[ h * T_d x ] } + noise`, with latent object `x`, true translation `d`, optics `h`, pixel integration `P`, radiometry `a,b`, quantization/clipping `Q`. The proposed forward model must state when it is an approximation: phase contrast, coherent effects, spatially varying optics, halos and material response are not automatically described by a positive Gaussian intensity blur.

Absolute position and relative motion are different objectives. With fixed optics, a shared boundary bias may cancel in a displacement difference. That does not make the recovered diameter or absolute position correct. Commanded stage motion remains a nominal reference until independently measured.

## 2. Chosen architecture direction

Use a small local predictor coupled to an explicit continuous image-formation and rendering module. Keep the measurement representation and the displayed reconstruction available separately, and test that the displayed image remains consistent with the representation. Merely putting physical names on unconstrained dense outputs is insufficient.

The predictor should expose: local geometry and orientation; position correction with uncertainty; edge transition/optical width; intensity and contrast; texture correction; and applicability/fit residuals. Calibration quantities come from a separate calibration record, not from test labels. All parameter units, bounds and coordinate signs are recorded. A neutral parameter setting must reproduce the input through a tested identity path.

Position is one displacement along a boundary profile, extended coherently over its normal neighborhood. Arbitrary pixel-dependent normal displacement is prohibited from being advertised as pure position: its normal derivative also changes width. Width acts around a shared, explicitly estimated edge anchor. For an isolated monotone continuous profile `J`, the candidate action is `J(c + g*(t-c-delta))`. Its midpoint becomes `c+delta` and its 10–90 width becomes `w/g` **only with a correct anchor and the stated continuous coordinate definition**.

R122 rejects direct pixel interpolation as a certified renderer: it fails the declared position/width tolerances. Next implementation should estimate a continuous local representation, render with sensor integration, and quantify the remaining numerical error. A fitted parameter can stay fixed while a pixel-derived midpoint changes; both must be reported rather than changing the metric to hide a discrepancy.

A 1D edge result is not a 2D image solution. The renderer must still handle curvature, corners, adjacent edges, polarity, textured plateaus, intersecting normals, patch boundaries and overlapping tiles. Use geometry-consistent local charts only where valid; keep unchanged output plus an explicit uncertainty reason elsewhere. Finite receptive fields and a sufficient halo must give matching retained pixels under different tile origins/sizes. This has not yet been implemented or passed in R122.

Texture must remain a supported capability. Do not restore it as an unrestricted additive path that can silently cancel position or width. Log before/after texture output, its effect on geometry readouts and forward residual, and constrain it using known texture truth on independent synthetic sources. Zero mean or high-pass alone is insufficient (R122 has a zero-integral counterexample). Orthogonality to position/width derivatives could reduce first-order coupling but is a hypothesis, not a proof of nonlinear independence. Do not silently replace all edge textures with ideal symmetric steps.

## 3. What learning can and cannot supply

Known training answers are legitimate supervision. The problem is using the same sample, acquisition, frame, derived crop, teacher output, SEM dimensions, or adapted ancestor model on both sides of an independence claim. Generate training truth independently of evaluation objects. Partition the source ancestry **before** crops, simulated motion, degradations, teachers or augmentation. Every auxiliary loader uses that same partition. Split roles or renamed files are not independent origins.

For synthetic sequences, translate the continuous object first; keep optics fixed within a sequence; integrate pixels afterward; then apply independent noise and declared gain changes. Vary object geometry, PSF width/asymmetry, radiometry, texture and motion independently when claiming their separation. Centered-PSF assumptions must be independently calibrated, not made true by renormalizing a measured shift away. Include deliberate out-of-model cases.

A source record must include item ID, split, physical sample/latent identity, acquisition/generation identity, full ancestor IDs, generator version/seed, calibration identity, truth type and units. Any pretrained weights require their ancestry too; otherwise begin from scratch. `scripts/split_guard.py` rejects missing histories and shared origins, including the actual V42 shared-frame record. It is an admission check, not independent proof of metadata truth or scientific fidelity.

Training must save the actual sample IDs drawn by **all** loaders and a bounded per-step ledger: input/target identities, augmentation/optics parameters, loss components and active modules. Save selected parameter maps and gradient/response checks. Verify actual loader consumption against the protocol before a longer run. This directly addresses the R119 gap between data existing and data actually entering training.

Single-image ambiguity cannot be eliminated by supervision. R122 gives identical observations for distinct object positions when PSF shift is unknown, for different intrinsic/optical widths, and for different detail after pixel integration. In those cases a prediction depends on assumptions or a prior. It must carry calibrated uncertainty or decline the unsupported correction; a sharper-looking image is not new physical evidence.

## 4. Acceptance sequence and stopping rules

1. **Operator prototype, no learning:** implement the continuous 2D renderer, identity, isolated position/width/texture actions, invertibility/local overlap rules and finite tile support. Compare to independent analytic integration and converged 2D rendering. Keep the R122 failed pixel and coarse-raster tests as permanent counterexamples. No new loss-weight search before this passes.
2. **Small prediction study:** after step 1, use a fixed small training budget with two initializations and one common development set. First compare to Raw and the explicit fit on independently generated truth. Recover known parameters and geometry/motion/texture together; demonstrate that disabling one function does exactly what its name says. This step is specified, not executed in R122.
3. **Calibration and practical usefulness:** calibrate relevant optics/material correspondence on separate sources; evaluate on new physical samples and acquisition sessions. Existing R119 SEM images, R121 diagnostic fixtures, R122 fixtures and V42 thesis samples are development/audit data. Do not describe them as unseen. The old 144-scene confirmation is consumed and cannot be reset by changing hashes or filenames.
4. **Independent confirmation:** freeze source, parameters, metrics, eligibility rules and thresholds before accessing fresh confirmation observations. Custody and access logging must be independent of the candidate runner; checksum consistency does not establish semantic correctness or blindness. Preserve errors and failed predictions in denominators. A failure stays a failure and cannot be turned into completion by updating expected evidence.

Every report gives absolute shape/position error, true-motion error, texture error against truth, confidence calibration, failure/coverage counts, and worst-case behavior by shape, scale, contrast and noise. Report raw and corrected outputs under the same coordinate/readout rules. Metrics are not substituted after seeing rankings. An average improvement with hard failures does not support an “any scene” claim.

## 5. Immediate concrete next work

Implement and verify the continuous **2D** renderer before another neural training run. R122 already provides executable 1D action tests, an explicit sensor-integrated edge fit, a repaired area-integrating simulator, source-lineage checks and adversarial examples. These are its starting tests, not an unseen benchmark. A clean synthetic prototype can proceed without V42; claims of usefulness on unknown real samples will require fresh independent physical observations.

The key unresolved questions are measurable: which optical/material model fits the intended microscope; how reliably the edge anchor and geometry can be inferred from one image; where normal charts fail; how to preserve real texture without changing geometry; and whether uncertainty predicts actual errors on independent observations. R122 has narrowed these questions, not answered all of them.

Related primary research supports checking reconstruction stability and uncertainty, while not proving this particular design: Antun et al. demonstrate instability and missed structures in learned inverse reconstructions ([2020 paper](https://arxiv.org/abs/1902.05300)); Liu et al. evaluate uncertainty and misuse detection for multi-frame structured illumination microscopy ([2025 paper](https://www.nature.com/articles/s41467-025-60093-w)). Their modalities and models differ from this project's single-image optical metrology; the design choice here is an inference from our local counterexamples, not a transfer of their performance claims.
