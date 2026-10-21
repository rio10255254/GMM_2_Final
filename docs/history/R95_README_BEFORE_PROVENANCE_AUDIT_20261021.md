# R95 Evidence-Conditional Scratch

R95 is the locked next-round design derived from the R93 failure analysis. It
is an independent scratch experiment, not an R93 checkpoint continuation.

## R95 repair applied before formal training

The final R95 preflight also found and repaired the mechanism that left R94
near identity: an epsilon floor made zero need nonzero, saturated need biases
combined with image-space L1 gave almost no useful gradient, EMA retained too
much initialization, and GPU cache was counted twice.  R95 uses exact-zero
targets, joint logit supervision on T/B/S, a gradual intervention handoff,
adaptive early EMA, incremental GPU headroom accounting and non-opposing
cross-objective updates.  The local tile-exact architecture is preserved.

## Core diagnosis

R93 asks a shared representation to improve detail, geometry, identity and
motion at the same time. Its current run shows motion and contour improving
while detail turns worse and clear-input change remains large. Direct branch
attribution also showed that the need/recoverability control could be used as a
shortcut and that the generator's local boundary-fade cause had been assigned
to the sharpening target.

R95 therefore follows the recorded formation order. It first removes sensor
nuisance, then corrects radiometry, then reverses spatially varying local
contrast fade, then restores a phase-safe structural boundary, and finally
restores material texture. Every learned tower is private; only fixed local
measurements are shared. Need and recoverability have separate towers and are
trained only from direct procedural truth.

## Data policy

The formal population remains 1,250 procedural scenes and 5,000 stored
observations. The audited R93 arrays are read directly. R95 does not regenerate
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

1. Epochs 1-6 learn intervention need, physical evidence and geometry only.
2. Epochs 7-14 learn each private branch from its exact causal target.
3. Epochs 15-26 move continuously from truth stage inputs to predicted stage inputs.
4. Epochs 27-40 train the complete predicted cascade with motion, repeated-noise,
   translation and overlap consistency.
5. Epochs 41-48 use the large 896/512 patch/core context at a low learning rate,
   without increasing the detail weight.

Candidate checkpoints are epochs 32-48 every two epochs. Selection first
removes statistically dominated candidates, then minimizes the worst
normalized regret across the locked axes. Real/SEM suites can reject the frozen
candidate but cannot choose a different epoch.

The GPU batch is calibrated immediately before training. The largest batch
that leaves at least 9 GiB for the desktop is selected, and gradient
accumulation preserves the scheduled effective scene batch. Fresh calibration
selected scene batches 4, 2 and 1 for 512, 768 and 896 pixel patches.

## Same-run interruption recovery

The original formal process was stopped after epoch 10 computation by the
9-GiB desktop reserve check; this was a policy stop, not a CUDA allocation
failure. Epoch 8 is the last committed checkpoint, so the authorized
continuation replays from epoch 9 within the same R95 run. It does not load any
R93, R94, teacher or external model state.

The continuation keeps the original patch sizes and target effective scene
batches. Low free-memory readings are now warnings rather than a reason to
discard the run. End-of-batch references and unused CUDA cache are released
before validation, every completed epoch writes a recoverable latest
checkpoint including optimizer and random state, and a true CUDA-memory
failure triggers a bounded clean-process retry with a smaller scene batch.
The initial epoch-8 checkpoint predates optimizer-state saving, so only this
first continuation restarts AdamW moments; that exception is recorded in the
continuation audit.

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

These are design and target-validity checks. They are not trained R95 results.

## Current state

The architecture and scientific strategy remain locked. The memory-policy
continuation is authorized only for the existing R95 run and is hash-bound to
its epoch-8 checkpoint. No second formal run is permitted.

## Folder guide

- `config`: the locked scientific and execution contract.
- `model`: the R95 cause-separated reconstruction architecture.
- `training`: exact counterfactual targets, stage replay and conflict-safe updates.
- `inference`: the one canonical full/tiled reconstruction path.
- `scripts`: reproducible diagnostic and design-audit entry points.
- `tests`: focused architecture and causality regressions.
- `reports`: generated evidence behind the locked decisions.
- `data`: reuse/isolation policy; no duplicated formal payload.
- `weights`: reserved for R95 scratch checkpoints only.

Start a new formal run with `scripts/start_formal_training.ps1`. Continue the
authorized interrupted run with
`scripts/start_formal_training.ps1 -ContinueInterruptedFormal`.

Open the fixed foreground dashboard by double-clicking
`Open_Training_Monitor.cmd`, or run `scripts/open_training_monitor.ps1`.
It shows live epoch and run ETA, GPU/VRAM/temperature, the latest training and
eight-role validation values, checkpoint/error health, and automatically
condenses itself when the terminal is narrow or short. It deliberately uses no
full-width separator rules. Closing the monitor does not stop training.

