# v16 Implementation Status

This file records the first concrete implementation step after the v16 handoff package.

## What Was Added

v16 now has a formal model/data candidate:

`r61_motion_texture_stepguard_v16_dualgate_boundary_focus`

The candidate keeps the v14 camera-texture motion backbone and adds a new procedural Step-like guard role:

`step_guard_motion_texture_synthetic`

This role is synthetic only. It does not use real Step images or real Step labels. It is intended to teach repeat-capture stability, 0.8 px small-step behavior, and 8 px commanded-step-like behavior without leaking the answer from the real Step dataset.

## Changed Code

| area | change |
|---|---|
| Dataset generator | Added `step_guard_v16` bias profile and `step_guard_motion_texture_synthetic` role |
| Dataset generator | Added `--step-guard-count` |
| Dataset generator | Added procedural Step-like motion cycle with repeat, 0.8 px, 8 px, and 20260603-like motion examples |
| Launcher | Added official v16 candidate |
| Launcher | v16 starts from v14 best checkpoint |
| Launcher | v16 uses R39 a970 as the region-KD teacher |
| Tests | Added v16 dataset, launcher, and no-real-Step-leakage checks |

## Formal v16 Dataset Package

Path:

`D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r61_universal_boundary_generalization\hs100mg_basler\r61_universal_boundary_train_motion_texture_step_guard_v16`

Manifest:

`D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r61_universal_boundary_generalization\hs100mg_basler\r61_universal_boundary_train_motion_texture_step_guard_v16\manifest.json`

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

Motion pair counts:

| type | pairs |
|---|---:|
| clean motion | 2400 |
| camera-texture motion | 2400 |
| Step-like guard motion | 1600 |
| total known-motion sequences | 6400 |

Leakage check:

- Step-like rows: 3200.
- Rows marked `no_real_sample_pixels=true`: 3200.
- Rows with `real_step_data_used` not false: 0.
- Label source: `known_synthetic_step_guard_motion_truth`.

## Verification Already Run

Targeted red-to-green tests:

- `python -m pytest -q .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\tests\test_prepare_r61_universal_dataset.py -k "step_guard_v16 or step_guard_motion_texture"` -> 2 passed.
- `python -m pytest -q .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\tests\test_launch_r61.py -k "stepguard_v16"` -> 2 passed.

Full R61 test suite:

- `python -m pytest -q .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\tests` -> 111 passed, 2 warnings.

Launcher dry-run:

- Candidate resolved.
- v16 data package loaded.
- v14 best checkpoint found.
- fixed split created with group overlap count 0.
- Step-like stage included in training and motion loader.

Smoke training:

`python .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\launch_r61.py --candidate r61_motion_texture_stepguard_v16_dualgate_boundary_focus --num-epoch 1 --batch-size 1 --val-batch-size 1 --seq-batch-size 1 --num-workers 0 --max-train-batches 1 --run-suffix smoke_v16_20260623`

Result:

- Completed.
- Loaded v14 best checkpoint.
- Loaded R39 a970 region-KD teacher.
- Stage 40 Step-like guard appeared in training include subdirs.
- Motion pairs were enabled.
- Wrote smoke weights.

Smoke run folder:

`D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_smoke_v16_20260623_20260623_195253`

## Next Required Run

The next step is the real 8-epoch training run. A suggested command is:

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = "D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\reports\training_logs"
python .\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\launch_r61.py `
  --candidate r61_motion_texture_stepguard_v16_dualgate_boundary_focus `
  --num-epoch 8 `
  --batch-size 4 `
  --val-batch-size 2 `
  --seq-batch-size 2 `
  --num-workers 2 `
  --run-suffix full_e8_20260623 `
  1> "$logDir\r61_motion_texture_stepguard_v16_full_e8_$ts.out.log" `
  2> "$logDir\r61_motion_texture_stepguard_v16_full_e8_$ts.err.log"
```

After that finishes, the candidate still needs the full three-layer validation:

- simulated diverse phantom boundary gate versus R39 and R8;
- 20260603 real-sequence reconstruction and motion check;
- Step center-crop reconstruction and motion check;
- triple gate summary.

Do not call v16 successful until those checks are complete.

