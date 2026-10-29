# Shape-Aware Edge Anchor Implementation Readout 20260706

## What Was Built

Implemented a new open displacement tool:

`Tools/Displacement_Algorithms/scripts/measure_shape_edge_anchor.py`

The tool measures displacement from boundary structure instead of raw texture. It works in two stages:

1. Build an edge-only shape template from the selected ROI.
2. Estimate subpixel motion from the edge map, then validate it with shape/chamfer matching.

This is intended for thesis cases where the reconstructed image should make boundaries easier to locate.

## Key Behavior

- Raw and reconstructed images can be evaluated with the exact same ROI and expected physical step.
- Low-confidence matches can be rejected instead of returning a precise-looking but unreliable number.
- Rejected/low-confidence steps still keep their attempted displacement, so all-step comparisons do not silently discard difficult Raw steps.
- The output CSV includes displacement, shape match score, overlap, ambiguity margin, and whether edge-phase refinement was accepted.
- Strict mode is available with `--require-edge-phase-refine` and `--min-score-margin-px`.

## Tests

Automated tests added:

`Tools/Displacement_Algorithms/tests/test_measure_shape_edge_anchor.py`

Covered cases:

- blurred square with 0.72 px / 0.18 px subpixel motion,
- repeated circular features with a narrow expected-motion search window,
- blank images that should fail instead of returning fake displacement.
- rejected low-confidence steps still preserve attempted displacement and enter all-step summary.

Verification:

```text
27 passed in 2.79s
```

## 100MG x_1um Smoke Test

Dataset:

`best_displacement_models_20260706\trusted_full_sequences`

ROI:

`x=1010, y=35, width=900, height=650`

Expected step:

`-14.492754 px`, equivalent to 1 um at 0.069 um/px.

Strict settings:

```text
--require-edge-phase-refine
--min-score-margin-px 0.001
--max-chamfer-px 6.0
```

The fair comparison uses all 49 attempted steps. Confidence coverage is reported separately and is not used to remove Raw steps from the main statistics.

| case | all steps | high-confidence steps | mean step um, all steps | std um, all steps | step error um, all steps |
|---|---:|---:|---:|---:|---:|
| Raw | 49 | 16 | 0.886481 | 0.092068 | 0.113519 |
| V28 | 49 | 49 | 1.006597 | 0.010707 | 0.006597 |
| V31 | 49 | 49 | 1.005682 | 0.010178 | 0.005682 |
| V35 | 49 | 49 | 1.006555 | 0.010691 | 0.006555 |
| V41 | 49 | 49 | 1.006555 | 0.010666 | 0.006555 |

## Interpretation

This first real-data smoke test should not yet be used as a final thesis-wide ranking.

The important result is that the all-step comparison now penalizes difficult Raw steps instead of silently discarding them. Under this rule, Raw is much less stable and its mean step is biased low, while all tested reconstructions stay close to the expected 1 um step.

The confidence coverage still matters, but as a separate quality signal: Raw only has 16 high-confidence boundary steps, while all tested reconstructions have 49.

That means this method can expose two related model advantages:

1. reconstructed boundaries are easier to read consistently,
2. when all steps are counted, reconstructed displacement is also closer to the commanded motion and much more stable.

## Next Use

Use this method as a thesis boundary-readability metric:

1. Main table: report all-step mean, all-step standard deviation, and all-step error.
2. Confidence table: report high-confidence coverage and failure reasons.
3. Keep phase correlation as a neutral control.
4. Keep GMF-like local fitting as an independent anchor check.
5. Do not use high-confidence filtering as the main comparison unless the same fixed step set is used for every case.
