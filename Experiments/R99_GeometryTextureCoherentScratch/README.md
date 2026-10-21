# R99 Geometry-Texture Coherent Scratch

R99 is one independent scratch experiment. It does not inherit R61, R92, R98,
or any other checkpoint. The model begins as an exact Raw identity and learns
four ordered actions: radiometry, signed contour transport, edge-profile repair,
and source-supported texture recovery.

## Start training

Double-click `Start_R99_Training.cmd`, or open
`training/run_full_training.py` in an IDE and press Run. Only one formal run is
allowed. The visible monitor may be closed without stopping the hidden trainer.

The editable experiment choices are in `config/experiment_design.json`. Measured
GPU batch choices are in `config/execution_policy.json`.

## Folder map

- `model`: the complete model definition.
- `training`: the formal trainer and the editable one-click Python entry.
- `inference`: phase-aligned full-image and tiled reconstruction.
- `config`: experiment design, diagnostics, and measured execution policy.
- `data`: only live preview images and the locked training-data reference.
- `weights`: smoke and formal checkpoints, separated by run.
- `runs`: the unique run registry, active state, logs, and summaries.
- `results`: reconstruction previews and compatibility preflight artifacts.
- `reports`: speed calibration and later validation results.
- `tests`: architecture, signed transport, data equivalence, and tile-parity tests.

## Data isolation

The 5,000 procedural observations are reused read-only from the already audited
R92 package to avoid another roughly 17 GiB copy. Its full content hash is
locked before training. No SEM image, HS100MG geometry, real contour, teacher,
pseudo-label, prior checkpoint, or optimizer state is available to the trainer.

## Training speed choices

The data path crops before warp and label expansion; the evaluated central crop
was verified pixel-for-pixel identical to the previous full-canvas path. Fixed
binomial filters use mathematically equivalent separable passes. BF16,
channels-last convolutions, fused AdamW, pinned loading, and measured batch sizes
are enabled. Expensive 896-pixel patches are interleaved in the final stage
instead of occupying every late epoch.
