# R102 Universal Detail Scratch

R102 is an independent, from-scratch microscopy reconstruction experiment. It
does not load any earlier model, teacher output, SEM image, or HS100MG sample
structure during training.

## What is kept together here

- `config` records the locked experiment and adjustable training settings.
- `data` contains only a small verified reference to the existing 5,000-view
  procedural package, the deterministic augmentation contract, and a locked
  validation list. The 16.9 GiB base package is not duplicated.
- `model` contains the complete R102 architecture.
- `training` contains the dataset reader, objectives, and the editable one-click
  formal training entry.
- `inference` contains the canonical tiled reconstruction path and a file/folder
  command-line runner.
- `evaluation` produces the eight-axis validation and fixed real-image previews.
- `tests` must pass before the single formal run can start.
- `runs`, `weights`, `previews`, `logs`, and `reports` receive all outputs without
  mixing them with source code.

## Manual use

1. Run `data/prepare_data.py` once if the base package is moved or re-audited.
2. Run `tests/preflight.py`; it checks isolation, exact identity initialization,
   gradients, short learning, sub-pixel response, tiled equality, and all three
   planned GPU stages.
3. Double-click `Start_R102_Training.cmd` for the only formal 48-epoch scratch
   run. It opens the compact dynamic monitor automatically.
4. Double-click `Open_Training_Monitor.cmd` at any later time to reopen the same
   monitor. Closing the monitor does not stop the trainer.

The formal trainer has no resume or checkpoint input. Editing the values in
`config/experiment.json` before the formal run is allowed, but the preflight
must then be rerun so the recorded design and measured capacity remain aligned.
