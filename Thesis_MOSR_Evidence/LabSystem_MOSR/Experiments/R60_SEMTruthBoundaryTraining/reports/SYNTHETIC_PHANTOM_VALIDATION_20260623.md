# Synthetic Phantom Boundary Validation - 2026-06-23

## Purpose

This validation checks whether the current best R60 boundary-focus checkpoint can recover known object boundaries on synthetic shapes that are not the training sample.

The phantom contains mixed dark and bright objects: circles, ellipses, rotated rectangles, an irregular polygon, and slanted bars. The sharp phantom is treated as ground truth. The input image is intentionally boundary-biased, blurred, gradient-shaded, and noisy. The reconstruction is then compared against the known ground-truth boundaries.

## Checkpoint

Current tested checkpoint:

`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r60_semtruth_boundary_focus_boundary_focus_e008_mtb064_20260622_20260622_020906/epoch_005.pth.tar`

PSF was disabled for this test through the inference flags used by the R60 runner.

## Main Run

Representative run:

`LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/reports/synthetic_phantom_validation/phantom_validation_20260623_010352`

Key outputs:

- Ground-truth sharp phantom: `truth_sharp.bmp`
- Biased/blurred input phantom: `input/synthetic_mixed_phantom.bmp`
- Model reconstruction: `recon/reconstruct_progress_epoch_005_in_input_20260622_020906/synthetic_phantom_boundary_focus_recon/synthetic_mixed_phantom.bmp`
- Boundary overlay: `phantom_boundary_overlay.png`
- Region metrics: `boundary_metrics.csv`
- Machine-readable summary: `summary.json`

Representative metrics:

| Image | Mean boundary error (px) |
|---|---:|
| Sharp truth self-check | 0.031 |
| Biased blurred input | 1.207 |
| Model reconstruction | 0.887 |

Mean improvement from biased input to reconstruction: **0.320 px**.

## Multi-Run Stability Check

Five synthetic validations were inspected: one representative run plus four repeated runs with changed seed, noise, and blur.

| Case | Input mean error (px) | Reconstructed mean error (px) | Improvement (px) |
|---|---:|---:|---:|
| Representative | 1.207 | 0.887 | 0.320 |
| Same blur, seed 4 | 1.21 | 0.89 | 0.32 |
| Same blur, more noise | 1.20 | 0.88 | 0.32 |
| Stronger blur | 1.21 | 0.88 | 0.34 |
| Weaker blur | 1.20 | 0.91 | 0.28 |

The average improvement is stable, but it is not uniform across boundary types.

## Polarity Breakdown

Across the five inspected runs:

| Boundary type | Input mean error (px) | Reconstructed mean error (px) | Interpretation |
|---|---:|---:|---|
| Dark objects | 1.27 | 0.51 | Strong improvement |
| Bright objects | 1.14 | 1.27 | Slightly worse |

## Interpretation

The current checkpoint does improve some synthetic out-of-sample boundaries, especially dark objects against a gray background. However, it does not show general boundary correctness across polarity and shape. Bright-object boundaries are not corrected and can become worse.

This means the model is not yet proven to be a general boundary reconstruction model. It appears to have learned a useful correction pattern for boundary types similar to the training signal, but not a polarity-invariant or shape-invariant boundary rule.

## Verification Commands

Unit tests:

```powershell
python -m pytest -q "Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/tests"
```

Result: `19 passed in 0.64s`

Syntax check:

```powershell
python -m py_compile "Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/scripts/run_synthetic_phantom_validation.py"
```

Result: passed.

Representative validation:

```powershell
python "Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R60_SEMTruthBoundaryTraining/scripts/run_synthetic_phantom_validation.py" --device cuda:0 --size 512 --bias-px 2.0 --blur-sigma 1.35 --noise-sigma 2.0
```

Result: completed and produced the run folder listed above.
