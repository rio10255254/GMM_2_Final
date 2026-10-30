# Lab Formal Training 100 Epochs - 2026-06-09

## What Was Completed

The first formal LabSystem R39/R40 training pass completed with the validated
Lab BADS PSF and Lab-only training data.

Both runs used the Lab-compatible inherited COMBO checkpoint and were launched
without `--force_fast_eval`.

## Runs

| Line | Data package | Pairs | Run folder | Result |
|---|---:|---:|---|---|
| R39 safe | `r39_shape_mix_safe` | 1240 | `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260609_173931` | Completed 100 epochs |
| R40 combo | `r40_micro_capacity_train` | 1300 | `training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260609_185153` | Completed 100 epochs |

## Validation Readout

Each run wrote 100 validation-log rows. Formal validation metrics are populated
on 50 even epochs. The final epoch, epoch 100, is validated and is the best
validation-quality epoch for both lines.

| Line | Best PSNR | Best SSIM | Best rec | Best validation epoch | Recommended validation-quality checkpoint |
|---|---:|---:|---:|---:|---|
| R39 safe | 33.4311 | 0.9808 | 0.0011846 | 100 | `epoch_100.pth.tar` or `weights/latest.pth.tar` |
| R40 combo | 29.0112 | 0.9394 | 0.0036557 | 100 | `epoch_100.pth.tar` or `weights/latest.pth.tar` |

## Checkpoint Interpretation

The automatically selected `best_tradeoff.pth.tar` files are not the best
validation-quality files in this pass:

| Line | Auto tradeoff best epoch | Auto-best note |
|---|---:|---|
| R39 safe | 21 | Earlier tradeoff selector, weaker validation quality than epoch 100. |
| R40 combo | 44 | Earlier tradeoff selector, weaker validation quality than epoch 100. |

Use `epoch_100.pth.tar` or `weights/latest.pth.tar` for the next
validation-quality inference pass. Keep `best_tradeoff.pth.tar` as an internal
selector artifact until the Lab external/sequence validation confirms whether
the earlier tradeoff choice is useful.

## Interpretation

R39 is the stronger first Lab candidate on the current validation split. It
finished with much higher reconstruction quality than R40 and kept improving
through epoch 100.

R40 still improved through epoch 100, but its score remains lower because the
package is a microscopy-capacity line rather than the conservative first
replacement candidate. It should be kept for later microscopy-feature and
averaging/fusion checks, not treated as the first standalone Lab winner.

## Verification

Completed checks:

- R39 and R40 dry-runs confirmed the Lab PSF, Lab data package, and 100-epoch
  configuration before training.
- Lab launcher and ring-package tests passed: 6 tests.
- Both formal runs completed to epoch 100.
- Both runs produced epoch checkpoints from 5 through 100, plus `latest` and
  final named weights.
- No Lab R39/R40 Python process remained after completion.

Observed non-blocking warning:

- MATLAB PSF loading emitted a duplicate variable-name warning from scipy. The
  same warning appeared during successful training and did not stop either run.

## Next Step

Run Lab inference and Lab validation using the epoch-100/latest checkpoints
first. Then compare against the auto tradeoff checkpoints only if the sequence
or external validation suggests the later validation-quality checkpoints hurt
measurement stability.
