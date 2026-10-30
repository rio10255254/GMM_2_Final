# v16 Full Training Status

## Summary

v16 has completed the intended full 8-epoch training run.

This means v16 is ready for validation. It does not mean v16 is ready to be used as a thesis result.

## Candidate

`r61_motion_texture_stepguard_v16_dualgate_boundary_focus`

## Full Training Run Folder

`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020`

## Best Checkpoint

`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020/weights/best_tradeoff.pth.tar`

## Training Logs

Main stdout:

`LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_stepguard_v16_full_e8_20260623_200012.out.log`

Stderr:

`LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_stepguard_v16_full_e8_20260623_200012.err.log`

The stderr log contains only the known MATLAB duplicate-variable warning from SciPy.

## Last Training Metrics

From epoch 8:

| metric | value |
|---|---:|
| validation total loss | 0.032344 |
| validation reconstruction loss | 0.005981 |
| validation edge loss | 0.040669 |
| validation PSNR | 21.99 |
| validation SSIM | 0.9437 |
| best tradeoff score | 136.4300 |
| best gmf objective | 136.4300 |
| training step std proxy | 0.4843 |
| outlier proxy | 0.0000 |
| step error proxy | 0.0000 |

These are training and internal validation numbers only.

## Data Package

`LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16`

Counts:

| role | rows |
|---|---:|
| legacy shape | 800 |
| SEM truth anchor | 1400 |
| sequence guard | 1200 |
| universal synthetic | 4096 |
| clean motion synthetic | 4800 |
| camera-texture motion synthetic | 4800 |
| Step-like camera-texture guard synthetic | 3200 |
| total | 20296 |

Leakage note:

The Step-like training rows are synthetic. They are meant to regularize repeat and step behavior without training on real Step answers.

## Verification Already Done

- Targeted v16 dataset and launcher tests passed.
- Full R61 test suite passed before training: 111 passed, 2 warnings.
- Launcher dry-run passed.
- v16 smoke training completed and wrote weights.
- Full 8-epoch v16 training completed and wrote `best_tradeoff.pth.tar`.

## Verification Still Needed

These are not complete yet:

- v16 simulated diverse phantom validation;
- v16 gate versus R39 and R8;
- v16 20260603 reconstruction and motion probe;
- v16 Step center-crop reconstruction and motion probe;
- v16 triple gate.

## Current Verdict

v16 is a trained candidate, not a proven result.

The next run should validate it before building another model.

