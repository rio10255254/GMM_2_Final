# R96 Localized Evidence Protected Scratch

R96 is one independent 44-epoch scratch experiment.  It keeps the proven local,
tile-exact model structure and changes the learning strategy that caused the
previous late-stage detail regression.

## What changed

- Need/evidence controls are learned and measured per channel, so different
  channel baselines cannot imitate local discrimination.
- Local contrast, boundary and texture targets use smooth support-aware
  supervision.  Pixels carrying a real target stay visible without using a hard
  binary mask, while quiet regions are still trained to remain quiet.
- From epoch 27 onward, all five private branch objectives are protected
  individually during joint output, motion, repeated-noise and translation
  training.  A global objective cannot reverse one branch merely because the
  sum of all branch losses still improves.
- Every eighth batch adds a clean counterfactual from the same procedural
  population, broadening identity protection beyond one clear-data role.
- The run ends at epoch 44.  The final stage is consolidation, not a late
  detail-weight escalation.

## Independence and data

The model, optimizer and random state start fresh with seed 960041.  No R95 or
earlier checkpoint, teacher, pseudo-label or optimizer is loaded.  The audited
1,250-scene/5,000-observation procedural package is read by its locked hash and
is not duplicated.  Real microscopy and SEM pixels remain validation-only.

## Verified before launch

- 6 focused tests passed.
- 17 architecture/routing checks passed.
- Full reconstruction and canonical tiled reconstruction are exactly equal.
- 64 hidden-stage replays are pixel exact and all crop labels are exact.
- The complete 838-view capacity and oracle audits pass.
- The locked 100-image ACM clean-target direction remains positive.
- A real 896/512 late-phase update passed with all five private gradients finite,
  nonzero and non-opposing; peak reserved VRAM was 19.78 GiB on the A6000.

## Use

Run `scripts/start_formal_training.ps1` to start the sole formal run.  Open the
fixed foreground dashboard with `Open_Training_Monitor.cmd`.  All checkpoints,
previews, logs, progress records and reports stay inside this experiment folder.

