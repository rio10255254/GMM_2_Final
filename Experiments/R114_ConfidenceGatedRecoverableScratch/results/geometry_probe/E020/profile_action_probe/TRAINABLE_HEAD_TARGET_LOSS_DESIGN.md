# R114 Boundary Profile Action: Trainable Design

## Causal result

- Action-library capacity supported: **True**
- Repairs all three failure families over frozen Full: **True**
- Preserves halo and uneven families: **True**
- This probe is an oracle upper bound and is not deployable.

## Allowed runtime action

Keep the existing local SDF and normal controller. Add one profile head with four bounded maps: midpoint offset, signed plateau contrast, profile width, and visibility/reliability. The renderer remains analytic:

`profile = midpoint + 0.5 * signed_contrast * tanh(sdf / width)`

Blend this proposal only inside a predicted narrow boundary band. Do not add a free RGB/gray residual branch.

## Synthetic targets

1. SDF and normal: exact mask-derived geometry already used by the controller.
2. Midpoint: robust median of clean inside/outside normal-profile plateaus, expressed as an offset from the same raw-derived local midpoint cue used at inference.
3. Signed contrast: clean plateau difference, polarity preserving, clipped to the renderer range.
4. Width: robust 10-to-90 percent transition width fitted along the clean SDF normal; clamp to the analytic renderer range.
5. Visibility target: one only where the bounded analytic profile has lower locally smoothed truth error than identity/geometry Full; zero elsewhere. Store it as a soft, feathered map.
6. Reliability target: down-weight ambiguous normal samples, crossed plateaus, low signed contrast, and places where several shapes are inside one sampling radius.

## Heads and bounds

- midpoint_offset_gray: tanh bound, recommended +/-24 gray levels.
- signed_contrast_gray: polarity-preserving, recommended magnitude 4-72 gray levels.
- profile_width_px: sigmoid bound, recommended 0.8-3.5 px.
- profile_visibility: sigmoid 0-1, multiplied by boundary confidence, correction need, and recoverability.
- analytic action delta: retain a hard maximum of 48 gray levels and the 14 px outer band until a second ablation justifies relaxing either bound.

## Losses and schedule

- Parameter losses: masked smooth-L1 for midpoint, signed contrast, and width; each normalized per image before the batch mean.
- Visibility/reliability: focal BCE plus soft Dice in the boundary band; identity/clear samples explicitly target zero action.
- Profile loss: contrast-normalized 1D normal-profile loss at fixed distances, including transition midpoint and 10/50/90 percent positions.
- Physical guards: polarity consistency, monotonicity, no overshoot beyond predicted plateaus, zero action outside the band, and local-mean preservation outside the transition.
- Train the controller first. Then train the profile heads with the controller frozen or at a much lower learning rate. Only after both pass should a short joint stage be attempted.
- Alternate geometry and profile batches; do not simply add every objective into one permanent weighted sum.

## Required gate before formal training

A learned head must reproduce the oracle direction on a sealed synthetic split, preserve clear/flat identity, pass two-origin tile parity, and improve all three R74 failure families without losing the halo and uneven gains. The current oracle result only authorizes a learned profile-head probe, not a formal R114 model.
