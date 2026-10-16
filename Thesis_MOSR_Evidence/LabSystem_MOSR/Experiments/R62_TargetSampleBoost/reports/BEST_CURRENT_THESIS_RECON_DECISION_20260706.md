# Best Current Thesis Reconstruction Decision 20260706

## Decision

Current best thesis reconstruction mode is `v7_anchor_blend10`.

This is the safest current candidate because it gives a large 100MG edge-phase displacement recovery while staying stable under both GMF checks:

- fixed original GMF ROI: best overall score, no guardrail regression
- shape-aware square GMF ROI: best overall score, no guardrail regression
- image quality: very close to Raw, with only small added detail

Do not promote V22 for long training as-is. The short V22 probe preserved square shape but made 5x local GMF matching worse.

## Why Not R61 Alone

R61 is still strong for the original small-dot GMF center fitting, but it changes the 5x square/block shape too much.

Under shape-aware square GMF, R61 becomes the worst candidate:

| case | guardrail mean improvement | worst guardrail |
|---|---:|---:|
| `v7_anchor_blend10` | +2.080% | 0.000% |
| `v17e3` | +1.827% | -0.022% |
| `v20e1m200` | +1.280% | -0.037% |
| `r61` | -70.252% | -264.483% |

## Fixed Original GMF ROI

This uses the original local feature fitting ROI. It checks whether the reconstruction damages the prior dot/pillar center readout.

| group | Raw std um | `v7_anchor_blend10` std um | improvement |
|---|---:|---:|---:|
| 100MG x_1um | 0.009391 | 0.009392 | -0.009% |
| 100MG x_0p5um | 0.052039 | 0.052010 | +0.055% |
| 20x_1um | 0.025569 | 0.025489 | +0.315% |
| 20x_0p5um | 0.076249 | 0.076219 | +0.039% |
| 5x_1um | 0.185078 | 0.159571 | +13.781% |
| 5x_0p5um | 0.041139 | 0.017217 | +58.150% |

## Shape-Aware Square GMF ROI

This keeps 100MG and 20x on the original ROI, but evaluates 5x using the square/block region where V17/V20 preserve the sample shape better than R61.

| group | Raw std um | `v7_anchor_blend10` std um | improvement |
|---|---:|---:|---:|
| 100MG x_1um | 0.009391 | 0.009392 | -0.009% |
| 100MG x_0p5um | 0.052039 | 0.052010 | +0.055% |
| 20x_1um | 0.025569 | 0.025489 | +0.315% |
| 20x_0p5um | 0.076249 | 0.076219 | +0.039% |
| 5x_1um | 0.158455 | 0.158290 | +0.104% |
| 5x_0p5um | 0.013996 | 0.012896 | +7.863% |

## Phase Check

The large win is on 100MG edge-phase displacement, where Raw nearly fails to see the commanded motion.

| group | Raw median/std um | `v7_anchor_blend10` median/std um |
|---|---:|---:|
| 100MG x_1um | 0.0297 / 0.4342 | 1.0055 / 0.0110 |
| 100MG x_0p5um | 0.0518 / 0.4058 | 0.5000 / 0.0508 |
| 20x_1um | 1.0053 / 0.0242 | 0.9999 / 0.0247 |
| 20x_0p5um | 0.4987 / 0.0780 | 0.4952 / 0.0766 |
| 5x_1um | 0.9073 / 0.1550 | 0.9160 / 0.1566 |
| 5x_0p5um | 0.5111 / 0.0162 | 0.5095 / 0.0157 |

## Image Quality Check

Across the six thesis displacement groups, `v7_anchor_blend10` stays very close to Raw:

- mean Sobel p95 ratio vs Raw: 1.105
- mean Laplacian detail ratio vs Raw: 0.976
- mean MAE to Raw: 1.865 gray levels
- mean SSIM to Raw: 0.9983

This means it adds a small amount of useful reconstruction detail without turning the image into a cartoon-like output.

## Current Technical Direction

Use `v7_anchor_blend10` as the current thesis-safe reconstruction output.

Use V17/V20 and the shape-aware square GMF profile as diagnostic evidence that square/block features can be valid displacement anchors, but do not long-train V22 as-is.

Next training direction should be native raw-anchored residual training. The model should learn the `blend10` behavior internally instead of relying on an external fusion step.

## Evidence Files

- Fixed original GMF ROI scoring: `fixedroi_anchor_modes_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md`
- Shape-aware square GMF scoring: `shape_aware_square_anchor_modes_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md`
- 100MG and 20x/5x phase check: `anchor_fusion_fast_phase_eval_20260706/fast_phase_summary.csv`
- Image quality check: `anchor_quality_metrics_20260706/anchor_quality_summary_sample10.csv`
- Formal shape-aware GMF script: `../scripts/run_thesis_gmf_like_gate.py --profile shape_aware_square`
