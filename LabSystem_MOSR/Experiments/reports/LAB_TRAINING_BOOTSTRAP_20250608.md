# Lab Training Bootstrap - 2026-06-08

## What Was Completed

This run connected the LabSystem MOSR area to the main project training core
without copying or renaming the model implementation.

Completed items:

- Added Lab R39 and R40 training launchers with the same main-project filenames:
  `launch_r39.py` and `launch_r40.py`.
- Mounted the validated Lab PSF from the fine pre-alignment calibration run.
- Mounted Lab-only R39/R40 data packages.
- Redirected training output into the LabSystem area, not the original project.
- Added automatic Lab-compatible checkpoint filtering so old project weights can
  be inherited while Lab PSF buffers are rebuilt from the Lab PSF.
- Verified with tests, dry-runs, 1-epoch smoke runs, and 25-epoch training runs.

## Checkpoint Handling

The original COMBO checkpoint stores PSF buffers from the old project PSF grid.
The Lab PSF currently has 25 fitted positions, so those old PSF buffers cannot
be loaded directly.

The Lab launchers now create a cached compatible checkpoint under:

`LabSystem_MOSR/Traing_Progress/_checkpoint_cache/`

Only these PSF buffers are removed from the inherited checkpoint:

- `physics_layer.PSFs`
- `physics_layer.PSF_mean`
- `physics_layer.PSF_center`
- `weak_psf_block.PSFs`

The learned model weights are kept, and the Lab PSF is rebuilt when the model is
created.

## Runs

| Candidate | Data package | Pair count | Run folder | Result |
|---|---:|---:|---|---|
| R39 safe | `r39_shape_mix_safe` | 1240 | `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260608_230815` | Completed 25 epochs |
| R40 combo | `r40_micro_capacity_train` | 1300 | `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260608_232503` | Completed 25 epochs |

Both runs loaded the Lab-compatible checkpoint and reported missing PSF buffers
only for the expected Lab PSF rebuild keys.

## Validation Readout

The 25-epoch runs used `--force_fast_eval`, so formal validation happened on
even epochs. Odd epochs have zero-filled validation columns and should not be
used for formal comparison.

| Candidate | Best validated PSNR | Best validated SSIM | Best saved validated checkpoint | Notes |
|---|---:|---:|---|---|
| R39 safe | 31.5080 at epoch 24 | 0.9708 at epoch 24 | `epoch_020.pth.tar` | Epoch 24 validates best but no epoch-24 checkpoint was saved. Epoch 20 is the saved post-threshold validated checkpoint. |
| R40 combo | 27.8989 at epoch 22 | 0.9236 at epoch 24 | `epoch_020.pth.tar` | Epoch 22/24 validate best quality, but epoch 20 is the saved post-threshold validated checkpoint. |

Important caveat: because `--force_fast_eval` skips odd validation epochs, the
`best_tradeoff.pth.tar` file may be overwritten by a skipped-validation epoch.
For formal thesis results, rerun without `--force_fast_eval`, or end on an even
validated epoch and explicitly select a validated checkpoint.

## Recommended Next Step

Use these launchers for the formal Lab training pass:

- R39 shape main line: `launch_r39.py --candidate r39_shape_mix_safe --num-epoch 100 --device cuda:0`
- R40 microscopy line: `launch_r40.py --candidate r40_micro_capacity_combo --num-epoch 100 --device cuda:0`

Do not add `--force_fast_eval` for the final thesis-grade comparison run.
