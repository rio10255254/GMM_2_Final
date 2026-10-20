# R97 folder map

- `config`: locked scientific design, execution policy and measured GPU calibration.
- `model`: the inference architecture only.
- `training`: dataset replay, direct targets, periodic position panel and scratch trainer.
- `inference`: the one canonical full/tiled reconstruction implementation.
- `scripts`: preflight, formal launcher and foreground monitor.
- `tests`: executable architecture, identity, phase, periodic and tiling checks.
- `data/live_validation`: four real images used only for visual previews during training.
- `reports`: root-cause record and preflight evidence.
- `runs`, `weights`, `results`, `logs`: generated execution records; initially empty except smoke evidence after preflight.

The 5,000 procedural arrays are read from their existing hash-locked package to avoid duplicating roughly the same large payload.
