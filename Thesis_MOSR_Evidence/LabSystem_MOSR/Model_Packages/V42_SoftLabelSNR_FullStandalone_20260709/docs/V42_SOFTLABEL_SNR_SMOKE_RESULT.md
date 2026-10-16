# V42 Soft-Label SNR Smoke Result

Date: 2026-07-09

## Purpose

This experiment keeps the formal V41 standalone model untouched and creates a
reversible branch for two suspected boundary-fidelity issues:

- pixel stair-step risk in teacher/label boundaries
- no explicit image-quality/SNR-aware response in the model

## Data Package

Source package:

`LabSystem_MOSR/Training_Data/r62_target_sample_boost/hs100mg_basler/r62_target_sample_boost_v13_measurement_view_safe_teacher`

Experiment package:

`LabSystem_MOSR/Training_Data/r62_target_sample_boost/hs100mg_basler/r62_target_sample_boost_v14_softlabel_snr_smoke`

Smoke package size:

- 180 image pairs
- 15 roles
- 12 pairs per role
- all available geometry and motion metadata sidecars copied

Soft-label rule:

- source images are copied unchanged
- labels are Gaussian-smoothed only inside a narrow edge band
- original V41 data package is not modified

## Model Change

The main model now has an optional `quality_gate` branch.

- default: disabled, so old V41 behavior is unchanged
- V42 smoke: enabled
- base checkpoint: V41 standalone `best_tradeoff.pth.tar`
- trainable parts: `quality_gate`, `boundary_adapter`, `p1`, `out`

## Smoke Training

Final smoke run:

`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_v42_softlabel_snr_smoke_softlabel_snr_smoke_e2_mtb8_20260709_20260709_163730`

Settings:

- epochs: 2
- max train batches per epoch: 8
- batch size: 2
- device: CUDA GPU
- AMP: off

Result:

- training completed
- `best_tradeoff.pth.tar` was updated at epoch 2
- checkpoint contains `quality_gate` weights
- checkpoint model config records `quality_gate.enable = true`

Key smoke metrics:

| Metric | Epoch 1 | Epoch 2 |
|---|---:|---:|
| Train rec loss | 0.021109 | 0.014255 |
| Train grad loss | 0.117265 | 0.080000 |
| Train edge-orientation loss | 0.096212 | 0.076826 |
| Validation total | skipped | 0.089575 |
| Validation SSIM | skipped | 0.823411 |
| Sequence validation score | 0.795095 | 0.795096 |

Interpretation:

This is a pipeline smoke test, not a final model ranking. The new branch and
soft-label package train cleanly, save correctly, and do not collapse the
monitor output. The run is too short to claim a real performance improvement.

## Verification

Passed:

- `V42_SoftLabelSNR/tests/test_softlabel_quality_gate.py`
- `V41_Standalone/tests/test_launch_v41_standalone.py`

Total:

- 8 tests passed

Clean-up:

- failed/redundant 1-epoch V42 smoke output folders were removed
- only the final 2-epoch smoke output folder was kept
