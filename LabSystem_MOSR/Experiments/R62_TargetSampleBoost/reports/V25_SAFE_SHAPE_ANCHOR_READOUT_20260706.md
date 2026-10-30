# V25 safe shape-anchor readout

## Decision

V25 is useful as a diagnostic and partial improvement, but it is not strong enough to replace the current safe
`blend10` / V24 reconstruction path as the thesis-facing default.

The key reason is that V25 preserves the low-magnification square shape well and improves several 20x/5x guardrail
groups, but it does not improve the main 100MG displacement groups. Longer V25 training improves one 5x group but
does not produce a clearly better all-around checkpoint.

## What Changed

- Added `r62_target_selfshift_anchor_blend_safe_v25`.
- V25 starts from the V24 built-in anchor-blend checkpoint instead of bare R61 or V20.
- V25 keeps `raw_anchor_output_mode=blend` with `alpha=0.10`, so the low-magnification square does not collapse like
  the R61/V23-style outputs.
- Added anchor-teacher training data while keeping the low-magnification square raw-shape guard.
- Added a checkpoint interpolation utility for model-level V24-to-V25 weight averaging.

## Verification Summary

R62 tests:

- `56 passed, 2 warnings`
- Warnings are protobuf deprecation warnings only.

V25 E1:

- Fixed ROI rank: second, close to `blend10`.
- Shape-aware ROI rank: third, better than V24 but with one 5x guardrail regression.
- Low-magnification square shape remains close to Raw and V24.

V25 E3:

- Fixed ROI rank: worse than V25 E1.
- Shape-aware ROI rank: second, no guardrail regressions.
- Square shape remains good, but moves slightly farther from Raw than V25 E1.

V25 weight interpolation:

- `mix025` nearly matches `blend10` in fixed ROI scoring.
- `mix025` and `mix050` do not beat `blend10` under the square-aware ROI gate.
- Interpolation is not promoted as the current best.

## Key Numeric Evidence

Low-magnification square fidelity against Raw:

| group | case | mean absolute difference | edge similarity |
|---|---|---:|---:|
| 5x_1um | R61 | 15.608 | 0.847 |
| 5x_1um | V24 | 1.877 | 0.995 |
| 5x_1um | V25 E1 | 1.893 | 0.995 |
| 5x_1um | V25 E3 | 1.965 | 0.994 |
| 5x_0p5um | R61 | 15.671 | 0.850 |
| 5x_0p5um | V24 | 1.895 | 0.995 |
| 5x_0p5um | V25 E1 | 1.911 | 0.995 |
| 5x_0p5um | V25 E3 | 1.986 | 0.994 |

GMF-like candidate ranking:

| gate | best | best trained/safe checkpoint | note |
|---|---|---|---|
| fixed ROI | blend10 | mix025 | mix025 is close but not better |
| square-aware ROI | blend10 | V25 E3 | V25 E3 has no square-aware guardrail regression |

## Current Recommendation

Use `blend10` / V24 as the clean current thesis-facing reconstruction path. Keep V25 E1 and V25 E3 as supporting
evidence that the model can be strengthened without destroying the square shape, but do not promote them as the final
best model yet.

The next useful attempt should not be a longer V25 run. It should add a primary 100MG selection constraint or direct
primary-ROI weighting so that the 100MG groups cannot drift while optimizing the 20x/5x guardrails.
