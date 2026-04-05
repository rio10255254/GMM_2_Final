# R33 robust_p90 Results (2026-04-05)

## Training
- Candidate: `r33_robust_p90` (ROBUST_LOSS_PERCENTILE=0.90, WARMUP=10)
- Epochs: 100, Best: epoch 23
- Checkpoint: `Traing_Progress/training_progress_..._20260405_073906/weights/best_tradeoff.pth.tar`

## Key Findings

### 0.8px Main Battlefield — Significant Internal Improvement

| Metric | R30 | R33_p90 | Delta | Status |
|--------|-----|---------|-------|--------|
| **internal step_std_y** | 0.2050 | **0.1459** | **-28.8%** | Breakthrough |
| inner residual_std | 2.8939 | **2.4224** | **-16.3%** | Major gain |
| inner improvement | 56.16% | **63.32%** | **+7.16pp** | Major gain |
| outer residual_std | 2.5987 | 2.7649 | +6.4% | Slight regression |
| outer improvement | 59.71% | 57.13% | -2.58pp | Slight regression |

### 0.08px — Same Pattern

| Metric | R30 | R33_p90 | Delta |
|--------|-----|---------|-------|
| **internal step_std_y** | 0.1621 | **0.1189** | **-26.7%** |
| **inner residual_std** | 2.9153 | **2.3943** | **-17.9%** |
| outer residual_std | 2.6084 | 2.7428 | +5.2% |

### 8px — Regression (Macro Guard Risk)

| Metric | R30 | R33_p90 | Delta |
|--------|-----|---------|-------|
| step_std_y | 0.1985 | 0.2063 | **+3.9%** |
| outer residual_std | 2.4679 | 3.3581 | **+36.1%** |
| k2 verdict | stable_offset | **moderate** | Degraded |

## Interpretation

Winsorize at p90 successfully redirected model capacity toward inner boundary:
- Inner residual_std dropped 16-18% (exactly the target)
- Internal step_std dropped 27-29% (far beyond expectations)
- But outer boundary and 8px dataset regressed — p90 is too aggressive

## Next Step

Run p95 (cap only top 5%) to seek a balance between inner gains and outer stability.
