# Design decision

## What this probe changes

Only the final renderer contract changes.  The extension predicts a carrier no
larger than 9 gray levels, applies the existing local edge support, and subtracts
a local Gaussian mean.  The resulting correction is therefore local, high-pass,
and mathematically bounded to 18 gray levels.  It can restore fine contour and
texture evidence but cannot rewrite broad illumination or create an unrestricted
image residual.

## What this probe deliberately does not change

- detector, renderer backbone, width and shift heads;
- source cues, receptive field, scratch seed, data, batches, steps, or base loss;
- single-image use or tile-safe inference;
- no real/SEM labels, no V42/R61/R109 checkpoint, no teacher;
- no GMF optimization and no CD-led selection.

Both arms include the same detail head, so each has 678,340 parameters.  In the
baseline the projected detail is multiplied by zero.  The smoke run confirmed
identical initial and post-detector state hashes.

## Why there is no low-resolution-control arm

The R113 known-truth ceiling found a worst contour error of 9.17 px for smoothed
controls, compared with 3.24 px for dense width-plus-shift controls.  Adding a
third learned arm would make the first causal test larger while testing a
mechanism that already failed its no-training upper-bound screen.

## Formal probe size

- 1,024 family-balanced synthetic training scenes;
- 128 family-balanced synthetic validation scenes;
- eight epochs: two detector, six renderer;
- batch size six, same order and step count for both arms;
- 24 locked R113 paired-condition cases evaluated after training;
- at least 7 GiB free GPU memory required before either arm starts.

This is intentionally a mechanism probe, not a new R114 candidate.  A later full
experiment is authorized only if the bounded-detail arm improves hard-case
contour or high-frequency recovery without worsening identity, tile parity,
same-shape condition consistency, or different-shape retention.

## Current state

The first matched formal pair is complete.  The bounded branch used only 0.125
gray levels: worst contour error and same-shape condition consistency improved,
while mean boundary and high-frequency errors regressed slightly.  This supports
one final scratch arm with direct staged supervision, not a larger model or
inherited weights.

`bounded_detail_supervised` recomputes the residual after the current detached
base output, maps it through the exact same source support, half-bound carrier,
and local high-pass projection, and sets its target to zero on identity samples.
Its weights across the six renderer epochs are `2.0, 1.5, 1.0, 0.65, 0.40,
0.25`; all original physical losses remain active throughout.  A carrier-level
auxiliary target prevents the zero-local-mean projection from cancelling the
early learning signal; it does not alter the deployed output formula.

After these scaffold and smoke checks passed, the supervised formal run was
authorized and launched once by the parent task.  No second run is permitted.
