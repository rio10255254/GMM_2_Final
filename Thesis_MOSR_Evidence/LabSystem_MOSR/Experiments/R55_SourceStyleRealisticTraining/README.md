# R55 Source-Style Realistic Training

R55 trains the Lab model on the R55 source-style rebuild of the R53 package.
The goal is to test whether removing the fake high-contrast label style improves
real Lab checkboard edge and corner reconstruction while keeping the R53
training recipe stable.

## Status

- Data package: rebuilt before this experiment
- Geometry sidecars: prepared by `scripts/prepare_r55_geometry.py`
- Training launcher: `scripts/launch_r55.py`
- Smoke training: passed
- Formal training: completed as a 50-epoch scratch run, batch 16, 4 workers, PSF-forward loss disabled
- Real checkboard validation: best_tradeoff passed the Lab R40 corner gate; latest failed

## Training Data Plan

The first formal run uses the repaired R53-style core package only:

- Train package: `LabSystem_MOSR/Training_Data/r55_source_style_rebuild/r53_realistic_dataset_calibration/r53_realistic_calibrated_train_6000`
- Held-out repaired package for later visual checks: `LabSystem_MOSR/Training_Data/r55_source_style_rebuild/r53_realistic_dataset_calibration/r53_realistic_calibrated_val`

The larger 51k repaired pool is kept as an expansion pool. It is not mixed into
the first R55 formal run so the comparison against R53 stays readable.

## Active Training

- Log pointer: `results/formal_training_logs/latest_formal_training_log.txt`
- Training root: `LabSystem_MOSR/Traing_Progress`

## Current Result

R55 best_tradeoff is the first Lab-system candidate in this line to pass the
local real-checkboard corner gate against the Lab R40 control. It is ready for
external GMF follow-up. The latest checkpoint is not usable because it regressed
the same real-corner metrics.

## Formal Run Command

```powershell
C:\Users\Rio\anaconda3\python.exe -u .\LabSystem_MOSR\Experiments\R55_SourceStyleRealisticTraining\scripts\launch_r55.py `
  --candidate r55_source_style_r53_scratch `
  --num-epoch 50 `
  --batch-size 16 `
  --val-batch-size 4 `
  --num-workers 4 `
  --seq-batch-size 4 `
  --run-suffix formal_source_style_e050_b016_w04_nophys
```
