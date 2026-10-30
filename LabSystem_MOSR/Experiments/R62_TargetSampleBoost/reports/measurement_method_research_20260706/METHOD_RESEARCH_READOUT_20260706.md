# Measurement Method Research Readout 20260706

## Completion Standard

This research pass is considered useful only if the proposed method satisfies all of the following:

1. It can be run inside the project without relying on the external company GMF program.
2. Raw and reconstructed images use the same ROI, same frames, and same rules.
3. The measured value is tied to the same physical structure, not whichever repeated pillar or edge happens to match best.
4. It can reveal boundary reconstruction improvements instead of only measuring whole-image texture similarity.
5. It reports failure or low confidence instead of silently returning a precise-looking wrong displacement.

## Why The Fixed ROI Boundary Projection Failed

The fixed ROI boundary projection method collapses a 2D image into a 1D signal before estimating displacement. That is too fragile for the current samples.

Main failure modes:

- Repeated pillar or grid structures can produce several nearly identical matches.
- A fixed ROI contains different partial structures after motion, especially near the ROI border.
- Projection averages away the exact feature identity, so the method can shift to a similar neighboring edge.
- At 5x, 0.5 um is only about 0.72 px, so any small bias from smoothing, edge thickening, or ROI composition becomes a large fraction of the displacement.
- Reconstruction changes edge contrast and edge thickness, so the projection peak can move even if the true physical edge did not.

Conclusion: projection is a useful diagnostic, but not strong enough as the thesis main displacement proof.

## Methods Studied

### 1. Phase Correlation / DFT Registration

This is the strongest general-purpose subpixel registration baseline. It estimates the translation that best aligns two image patches in the Fourier domain.

Good:

- Very precise on clean translation.
- Already available in the project as the phase-correlation tool.
- Good as a control method to prove the sequence contains measurable motion.

Bad for this thesis claim:

- It mostly rewards whole-patch similarity.
- Raw images can win because they preserve natural camera texture.
- It does not directly prove that model-reconstructed boundaries are more useful.

Use: keep it as the neutral control, not the main model-advantage metric.

### 2. ECC / Lucas-Kanade Patch Alignment

These methods optimize direct image alignment in the spatial domain. They can estimate subpixel motion and can be restricted to a chosen ROI.

Good:

- More local than full-image phase correlation.
- Can be used on the same selected structure across Raw and reconstructions.
- Good for checking whether a selected patch moves consistently.

Bad:

- Still sensitive to intensity changes introduced by reconstruction.
- If the ROI contains repeated structures, it can still converge to a wrong local match.
- It does not directly distinguish better boundary from better texture.

Use: secondary cross-check, not the main thesis metric.

### 3. Local GMF-like Fitted Anchor

This is the best current in-project direction. It detects or seeds local features, fits a local center, and uses the common displacement of those features. The current project tool already supports intensity mode, edge mode, multi-feature mode, pairwise mode, and seeded tracking.

Good:

- Closer to the external GMF behavior, but open and reproducible.
- It can focus on local pillars, dots, or square/block features instead of the whole frame.
- Pairwise mode avoids long-sequence feature shrinkage.
- Edge mode is more tied to boundary reconstruction than intensity mode.
- Existing unit tests confirm it recovers known synthetic subpixel motion.

Bad:

- ROI and polarity are decisive.
- If reconstruction makes a feature disappear or changes the chosen feature identity, the result can fail.
- It needs a confidence gate: feature count, inlier count, fitted weight, and step plausibility.

Use: primary near-term method, but only with fixed feature selection and explicit quality gates.

### 4. Multi-Anchor Corner / Feature Tracking

This tracks many small local anchors with corner or optical-flow style tracking, then uses the median or a robust cluster of their displacements.

Good:

- More robust than using one edge or one feature.
- Can reject a few wrong anchors.
- Suitable for square/block features, corner-like structures, and local sample marks.

Bad:

- Raw camera noise can create extra corners that reconstruction removes.
- Needs the same anchor policy for every case to avoid cherry-picking.
- A generic corner detector may prefer texture over true boundary.

Use: good secondary method if anchor points are frozen from a common reference or manually chosen once.

### 5. Shape-Aware Edge / Chamfer Matching

This converts the ROI into an edge map and matches a known local shape, such as a square boundary, pillar edge, or circle edge, using distance-to-edge matching.

Good:

- Most directly aligned with the thesis claim: the model should improve boundary localization.
- Less dependent on absolute brightness.
- Can be designed so the same physical shape is tracked across the sequence.
- Can produce both displacement and shape-quality confidence.

Bad:

- Needs a reliable reference shape or first-frame template.
- Must handle repeated structures carefully.
- Not yet as mature in the project as phase and GMF-like tools.

Use: strongest next research direction for "model advantage", especially for the central square/block ROI and known circular pillars.

## Local Evidence From Current Project

Existing project results support the following:

- Phase correlation is reliable but often too strong as a baseline, so it hides reconstruction advantages.
- Fixed ROI projection can show tiny gains in selected cases but fails conceptually on repeated structures and subpixel 5x motion.
- GMF-like pairwise tracking removed the earlier catastrophic feature-loss artifact and gave fairer 100MG results.
- Edge-mode GMF-like measurement showed clearer V7 benefit on 100MG x_1um than intensity-only GMF-like measurement.
- Shape-aware square GMF profiles were more relevant for the 5x square/block region than the original dot/pillar ROI.
- Current best thesis-safe direction in prior reports was not raw R61 alone, but a position-preserving reconstruction view that adds only limited reconstruction detail while staying close to Raw.

## Recommended Ranking

1. Primary thesis metric: shape-aware edge/chamfer anchor tracking.
2. First cross-check: edge-mode local GMF-like fitted anchor.
3. Second cross-check: seeded multi-anchor corner/feature tracking.
4. Neutral control: phase correlation / DFT registration.

## Proposed Next Experiment

For each important dataset group, run the same four measurements on Raw and the selected reconstructions:

- 100MG x_1um
- 100MG x_0p5um
- 20x_1um
- 20x_0p5um
- 5x_0p5um
- 5x_1um only as diagnostic, because prior evidence says its nominal step is less trustworthy

For each group:

1. Freeze one ROI and one anchor definition before comparing models.
2. Use the exact same frames for Raw and all reconstructions.
3. Report median step, standard deviation, error from expected step, valid-step count, and rejected-step reason.
4. Add a confidence table: feature count, inlier count, template score, and whether the same physical feature was tracked.
5. Only claim a model advantage when it improves displacement without worsening the confidence gate or shape/CD check.

## Immediate Implementation Target

The most useful new tool would be:

`shape_aware_edge_anchor.py`

Expected behavior:

- User provides ROI or seed shape.
- The tool extracts a stable edge template from the first frame.
- Each next frame is matched by local 2D edge distance, not by 1D projection.
- The method reports displacement and confidence.
- Optional mode fits a circle or square edge after coarse matching to refine the subpixel position.

This should be tested first on synthetic blurred square/circle motion with known subpixel shifts, then on the 100MG and 20x/5x thesis sequences.

## Source Notes

- Guizar-Sicairos et al. support DFT-based efficient subpixel registration as a strong translation baseline.
- Evangelidis and Psarakis support ECC as a robust image alignment family.
- Lucas-Kanade and inverse-compositional alignment support local patch tracking and optical-flow style registration.
- Steger supports subpixel line/edge localization as a boundary-oriented measurement family.
- Chamfer/distance-transform matching supports shape-based edge matching when intensity is not the ideal signal.

