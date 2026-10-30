# V23/V24 Anchor-Teacher Decision 20260706

## Decision

Do not long-train V23 as-is.

Use `r62_v24_v7_anchor_blend10_builtin` as the clean current thesis reconstruction package for the July thesis displacement datasets.

V24 preserves the empirically best `v7_anchor_blend10` behavior inside the checkpoint metadata, so the reconstruction flow no longer needs a separate external fusion pass. The model weights are unchanged from the validated V7 checkpoint; only the fixed raw-anchor output rule is packaged into the checkpoint.

## What Was Tried

V23 was designed to make the model learn the current best `v7_anchor_blend10` output internally:

- new package: `r62_target_sample_boost_v7_anchor_blend10_teacher`
- added direct teacher frames: 1000
- added direct teacher motion pairs: 500
- teacher source: verified `v7_anchor_blend10` reconstructions
- label policy: direct teacher pixels, no R61 pseudo-label sharpening
- start checkpoint: V20 GMF-ROI guard
- output anchor: disabled, so this tests native model output

The short probe trained 1 epoch with 200 train batches.

## V23 Result

V23 improved some primary/fixed-ROI displacement numbers, but it damaged low-magnification square shape.

Shape-aware 5x square GMF:

| group | Raw std um | blend10 std um | V20 std um | V23 best std um | V23 latest std um |
|---|---:|---:|---:|---:|---:|
| 5x_0p5um | 0.013996 | 0.012896 | 0.013469 | 0.036286 | 0.047543 |
| 5x_1um | 0.158455 | 0.158290 | 0.156889 | 0.154083 | 0.157447 |

Square shape fidelity versus Raw:

| case | mean gray MAE | image corr | edge corr | edge ratio |
|---|---:|---:|---:|---:|
| V20 | 7.391 | 0.9813 | 0.9503 | 1.436 |
| blend10 | 1.884 | 0.9988 | 0.9932 | 1.056 |
| V23 best | 20.016 | 0.8784 | 0.7966 | 2.630 |
| V23 latest | 19.696 | 0.8822 | 0.8018 | 2.558 |

Interpretation: V23 is not safe for the thesis images because it over-sharpens and injects dot-like artifacts in the 5x square/block region.

## V24 Result

V24 packages the validated blend10 behavior into the checkpoint.

Checkpoint:

`LabSystem_MOSR/Traing_Progress/packaged_checkpoints/r62_v24_v7_anchor_blend10_builtin/r62_v24_v7_anchor_blend10_builtin.pth.tar`

Pixel equivalence versus the prior external blend10 folders:

| group | frame count | mean abs gray diff | max gray diff |
|---|---:|---:|---:|
| 100MG x_1um | 50 | 0.0385 | 1 |
| 100MG x_0p5um | 51 | 0.0376 | 1 |
| 20x_1um | 50 | 0.0519 | 1 |
| 20x_0p5um | 50 | 0.0525 | 1 |
| 5x_1um | 50 | 0.0543 | 1 |
| 5x_0p5um | 50 | 0.0549 | 1 |

Shape-aware GMF:

| group | Raw std um | blend10 std um | V24 builtin std um |
|---|---:|---:|---:|
| 100MG x_1um | 0.009391 | 0.009392 | 0.009383 |
| 100MG x_0p5um | 0.052039 | 0.052010 | 0.052017 |
| 20x_1um | 0.025569 | 0.025489 | 0.025461 |
| 20x_0p5um | 0.076249 | 0.076219 | 0.076264 |
| 5x_1um | 0.158455 | 0.158290 | 0.158721 |
| 5x_0p5um | 0.013996 | 0.012896 | 0.013155 |

## Evidence Files

- V23 training package:
  `LabSystem_MOSR/Training_Data/r62_target_sample_boost/hs100mg_basler/r62_target_sample_boost_v7_anchor_blend10_teacher`
- V23 short training:
  `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_anchor_blend_teacher_v23_v23_anchor_teacher_e1_mtb200_20260706_20260706_101149`
- V23 fixed ROI scoring:
  `v23_anchor_teacher_fixedroi_gmf_scoring_20260706`
- V23 shape-aware scoring:
  `v23_anchor_teacher_shapeaware_gmf_scoring_20260706`
- V23 square fidelity:
  `v23_anchor_teacher_square_shape_fidelity_20260706`
- V24 packaged checkpoint:
  `LabSystem_MOSR/Traing_Progress/packaged_checkpoints/r62_v24_v7_anchor_blend10_builtin/r62_v24_v7_anchor_blend10_builtin.pth.tar`
- V24 pixel equivalence check:
  `v24_builtin_vs_external_blend10_pixel_check_20260706.json`
- V24 fixed ROI scoring:
  `v24_builtin_fixedroi_gmf_scoring_20260706`
- V24 shape-aware scoring:
  `v24_builtin_shapeaware_gmf_scoring_20260706`

## Next Technical Direction

If native weight-only behavior remains required, do not continue V23 directly. The next native attempt needs a stronger low-magnification square-shape constraint and probably should keep a raw-anchor output guard during training/evaluation until the weight-only output is proven safe.

For thesis use right now, V24 is the safest clean package: it preserves the best observed displacement behavior while keeping the image close to Raw.
