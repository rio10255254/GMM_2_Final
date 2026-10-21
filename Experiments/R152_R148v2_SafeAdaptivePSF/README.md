# R152 — Safe Adaptive PSF Extension of R148v2

## Purpose

Preserve the validated R148v2 architecture and output while adding the paper's FFT, multi-PSF weighting, weighted fusion, residual scale and residual connection module.

## Preservation policy

- All 1,194,406 R148v2 parameters are loaded from the frozen step-8192 checkpoint and kept frozen.
- Only 12,699 new PSF-fusion parameters are trained.
- A deployment multiplier of zero reproduces R148v2 exactly.
- The final multiplier is selected from a fixed list that includes zero; every reported candidate must remain within 0.5% of the R148v2 synthetic development terms.
- PSF weights are allowed to remain close to equal. This experiment requires the module to exist and participate in computation; it does not require correct PSF identification.

## Completed run

The 8,192-update extension run in `runs/formal_8192` completed on 2026-09-28. The fixed development rule selected deployment scale 1.0, keeping the PSF module active. The full 930-frame, 8,370-circle real validation completed on 2026-09-29 and passed the final integrity audit. Displacement, diameter and contour values are practically unchanged from R148v2; runtime and GPU memory increase modestly. The single consolidated architecture and data record is `reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md`. The earlier training and real-validation reports remain available as supporting records.

The user's primary step-stability measure is the standard deviation of the 30 adjacent steps **within each scan**. Its 30-scan paired distribution, pooled result and improvement range are in `reports/R152_SINGLE_SCAN_STEP_SD_20260930.md`. This differs from the earlier same-step-across-scan repeatability field.

Run `python scripts/status.py` for a compact snapshot.
