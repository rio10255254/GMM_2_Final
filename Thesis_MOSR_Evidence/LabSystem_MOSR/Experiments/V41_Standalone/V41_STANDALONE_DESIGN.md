# V41-Standalone Training Design

## Purpose

V41-Standalone is the thesis-facing final model line.  It keeps the useful V41
loss design and target-sample data, but removes the confusing V20/V35/V41
checkpoint chain from the formal story.

## Thesis Story

The model is described as a two-stage training flow:

1. Universal boundary pretraining gives the network a stable boundary
   reconstruction base.
2. V41-Standalone final training uses the complete final measurement package to
   reinforce CD preservation, boundary localization, and displacement
   consistency.

This is intentionally different from the exploratory R62 chain.  The older V20,
V28, V35, and V41 runs are treated as design exploration, not as the thesis final
training process.

## Training Package

The standalone run uses the final package:

`LabSystem_MOSR/Training_Data/r62_target_sample_boost/hs100mg_basler/r62_target_sample_boost_v13_measurement_view_safe_teacher`

This package contains 11,254 training pairs and keeps both the older
generalization groups and the newer target-sample measurement groups.

Key included groups:

- SEM / real boundary anchors
- sequence guards
- synthetic motion and textured motion
- real target-sample pseudo boundary pairs
- real displacement motion pairs
- GMF ROI self-shift motion pairs
- low-magnification square/dot pairs
- multi-magnification raw motion guards
- stability/shape teacher pairs

## Model Start Point

The default starting checkpoint is R61 v16, the universal boundary model.  This
is used as a clean pretrained base.  The standalone launcher does not start from
V20, V35, or the previous one-epoch V41 checkpoint.

## Default Hyperparameters

| Item | Setting |
|---|---:|
| Learning rate | 1.2e-7 |
| Epochs | 16 |
| Batch size | 4 |
| Validation batch size | 2 |
| Number of workers | 2 |
| Optimizer | Adam |
| AMP | Off |
| Base loss | Huber-based composite loss |

## Default Command

From the project root:

```powershell
python .\LabSystem_MOSR\Experiments\V41_Standalone\scripts\launch_v41_standalone.py
```

For a detached long run with logs:

```powershell
.\LabSystem_MOSR\Experiments\V41_Standalone\scripts\start_v41_standalone_long_training.ps1
```

## Validation Intent

After training, the resulting checkpoint should be compared against Raw, R61
v16, and the exploratory one-epoch V41 on:

- 100MG CD maps for the 36 pillars and 36 holes
- cross-section profiles
- Step and lab-system displacement sequences
- 20x and 5x multi-magnification displacement data
- PSF on/off reconstruction behavior

