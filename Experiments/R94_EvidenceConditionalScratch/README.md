# R94 Evidence-Conditional Scratch

R94 is the locked next-round design derived from the R93 failure analysis. It
is an independent scratch experiment, not an R93 checkpoint continuation.

## Core diagnosis

R93 asks a shared representation to improve detail, geometry, identity and
motion at the same time. Its current run shows motion and contour improving
while detail turns worse and clear-input change remains large. Direct branch
attribution also showed that the need/recoverability control could be used as a
shortcut and that the generator's local boundary-fade cause had been assigned
to the sharpening target.

R94 therefore follows the recorded formation order. It first removes sensor
nuisance, then corrects radiometry, then reverses spatially varying local
contrast fade, then restores a phase-safe structural boundary, and finally
restores material texture. Every learned tower is private; only fixed local
measurements are shared. Need and recoverability have separate towers and are
trained only from direct procedural truth.

## Data policy

The formal population remains 1,250 procedural scenes and 5,000 stored
observations. The audited R93 arrays are read directly. R94 does not regenerate
or copy the 27 GB payload. Recorded seeds and a compact replay state expose the
hidden causal stages on demand.

No real 5x, 20x, 50x, HS100MG or SEM pixel, geometry, pseudo-label or teacher
output is eligible for training. Real images are preview-only until the
synthetic-validation checkpoint has been frozen.

## Locked architecture

The formal model width is 16 and the model has 2,303,717 parameters, close to
R93's model size. It retains the normalization-free local encoder/decoder,
anti-aliased resizing, direct bounded residual and canonical 192-pixel halo.

The boundary path uses 29 symmetric filters across small, medium and 33-pixel
scales. Its slowly varying signed mixture sharpens an existing transition and
cannot create a new local intensity extremum. Large directional filters use a
sparse symmetric representation that matched the dense reference in the full
838-view capacity audit.

The local-contrast path is separate from sharpening. It uses four local scales
and may recover only an evidence-supported expansion of observed local range;
it has no free image-painting residual.

## Locked training strategy

The single formal run is 48 epochs from a new random initialization:

1. Epochs 1-4 learn intervention need, physical evidence and geometry only.
2. Epochs 5-12 learn each private branch from its exact causal target.
3. Epochs 13-24 move continuously from truth stage inputs to predicted stage inputs.
4. Epochs 25-38 train the complete predicted cascade with motion, repeated-noise,
   translation and overlap consistency.
5. Epochs 39-48 use the large 896/512 patch/core context at a low learning rate,
   without increasing the detail weight.

Candidate checkpoints are epochs 32-48 every two epochs. Selection first
removes statistically dominated candidates, then minimizes the worst
normalized regret across the locked axes. Real/SEM suites can reject the frozen
candidate but cannot choose a different epoch.

The GPU batch is calibrated immediately before training. The largest batch
that leaves at least 9 GiB for the desktop is selected, and gradient
accumulation restores an effective scene batch of 16. Calibration and training
must not start while R93 owns the GPU.

## Verified prototype evidence

- Exact generator-stage replay: 64/64 stored noise-free views, zero gray-level error.
- Exact layer recomposition: maximum floating error 5.96e-8.
- Full-canvas versus patch-core labels: exact for boundary, local contrast and texture.
- Architecture contract: 17/17 checks pass, including initial identity, private
  parameters, no reconstruction shortcut into controls, exact tiled parity and
  translated branch output consistency.
- Full 838-view capacity audit: 96.63% boundary amplitude coverage with 0.91%
  optimistic unreachable error; local contrast and texture bounds cover 100%.
- Full 838-view truth ceiling: total pixel, texture and boundary error ratios are
  0.0423, 0.0683 and 0.2290 versus Raw. Motion proxy mean/p95 changes from
  0.1965/0.8204 px to 0.0303/0.1340 px.
- Locked R73 Chan-Vese ACM ceiling: clean truth improves IoU and boundary
  distance in 96/100 images; every shape family has positive median improvement.

These are design and target-validity checks. They are not trained R94 results.

## Current state

The architecture and strategy are locked. The complete trainer passed real
dataset smoke runs, same-scene T/B/S supervision is active, and GPU calibration
selected two images per microbatch for all three patch sizes. The 896-pixel
stage retained about 13.93 GiB, above the 9 GiB desktop reserve. The one formal
scratch run is authorized.

## Folder guide

- `config`: the locked scientific and execution contract.
- `model`: the R94 cause-separated reconstruction architecture.
- `training`: exact counterfactual targets, stage replay and conflict-safe updates.
- `inference`: the one canonical full/tiled reconstruction path.
- `scripts`: reproducible diagnostic and design-audit entry points.
- `tests`: focused architecture and causality regressions.
- `reports`: generated evidence behind the locked decisions.
- `data`: reuse/isolation policy; no duplicated formal payload.
- `weights`: reserved for R94 scratch checkpoints only.

Start the formal run with `scripts/start_formal_training.ps1`. Open the live
terminal monitor with `scripts/monitor_training.ps1`.
