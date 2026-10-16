# R109 Staged Midpoint-Width Scratch Model

R109 is the first full scratch package built from the R108G result. It uses one
input image and a tile-safe local operator. Boundary midpoint displacement and
transition-width correction are separate, monotonic factors. The model cannot
emit a free image residual and cannot exceed the local observed intensity
range.

The detector is trained first to locate boundaries and decide whether an
action is needed. It is then frozen. The renderer is trained second and cannot
change that decision. Parameter-field smoothness is learned during training;
there is no output-time smoothing filter.

The package contains data preparation, model, training, inference, validation,
PowerShell launchers, logs, weights and previews under this one directory. All
formal weights start from random initialization. Real microscope, SEM,
HS100MG, R73 and R74 pixels are validation-only.

## Quick use

1. Run `scripts/prepare_data.ps1` once.
2. Run `scripts/validate.ps1`.
3. Run `scripts/smoke_test.ps1` for a short detector-plus-renderer test.
4. Run `scripts/train.ps1` for the single formal 48-epoch scratch run.
5. Run `scripts/monitor_training.ps1` in another PowerShell window.

The prepared data are hard-linked from the verified R107 5,000-scene package,
so they appear inside this project without consuming a second 1.35 GB. The
files remain valid even if the older directory is later removed.

