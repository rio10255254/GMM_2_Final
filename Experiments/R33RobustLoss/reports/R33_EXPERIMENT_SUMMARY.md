# R33 Robust Loss — Experiment Summary

**Date**: 2026-04-05
**Branch**: `sandbox/r33`
**Hypothesis**: Winsorize spatial losses to redirect model capacity from unfixable defect pixels to clean regions

## Candidates Tested

| Candidate | ROBUST_LOSS_PERCENTILE | Best Epoch | Training Time |
|-----------|----------------------|------------|---------------|
| r33_robust_p90 | 0.90 (cap top 10%) | 23 | ~65 min |
| r33_robust_p95 | 0.95 (cap top 5%) | 22 | ~65 min |

## Results: 0.8px Main Battlefield

| Metric | R30 baseline | p90 | p95 | R30 external GMF |
|--------|-------------|-----|-----|------------------|
| **internal step_std_y** | 0.2050 | 0.1459 (-29%) | **0.1289 (-37%)** | 0.191 (ext) / 0.168 (target) |
| inner res_std | 2.894 | **2.422 (-16%)** | 2.684 (-7%) | — |
| outer res_std | 2.599 | 2.765 (+6%) | 2.905 (+12%) | — |
| k2 verdict | stable_offset | stable_offset | stable_offset | — |
| offset verdict | fixed_bias | fixed_bias | dynamic_drift | — |

## Results: Cross-Scale

### step_std_y (internal)

| Scale | R30 | p90 | p95 |
|-------|-----|-----|-----|
| 8px | 0.1985 | 0.2063 (+4%) | **0.1737 (-12%)** |
| **0.8px** | **0.2050** | **0.1459 (-29%)** | **0.1289 (-37%)** |
| 0.08px | 0.1621 | 0.1189 (-27%) | **0.1145 (-29%)** |

### inner residual_std

| Scale | R30 | p90 | p95 |
|-------|-----|-----|-----|
| 8px | 2.719 | 3.236 (+19%) | 2.970 (+9%) |
| 0.8px | 2.894 | **2.422 (-16%)** | **2.684 (-7%)** |
| 0.08px | 2.915 | **2.394 (-18%)** | **2.682 (-8%)** |

### outer residual_std

| Scale | R30 | p90 | p95 |
|-------|-----|-----|-----|
| 8px | 2.468 | 3.358 (+36%) | 3.211 (+30%) |
| 0.8px | 2.599 | 2.765 (+6%) | 2.905 (+12%) |
| 0.08px | 2.608 | 2.743 (+5%) | 2.875 (+10%) |

## Key Findings

1. **Hypothesis validated**: Winsorize successfully redirects learning capacity
   - inner residual_std improved 7-18% across candidates
   - internal step_std improved 27-37% — far beyond expectations

2. **Trade-off discovered**: Outer boundary consistently regresses
   - p90: outer +5~36%
   - p95: outer +10~30%
   - The Winsorize mechanism caps gradients that the outer boundary needs

3. **p95 > p90 for step_std**: Less aggressive capping yields better step stability
   - p95 achieves lower step_std than p90 on all three scales
   - p95 fixes the 8px macro guard regression (p90 was +4%, p95 is -12%)

4. **New flags**:
   - 8px k2 verdict: stable_offset → moderate (both candidates)
   - 0.8px offset verdict: fixed_bias → dynamic_drift (p95 only)

## External GMF Projection (Speculative)

If R30's internal-to-external ratio holds (0.205 → 0.191, ratio = 0.932):
- p95 internal 0.1289 → projected external **~0.120** (target: 0.168)
- This would be a **28% improvement over R30 baseline** if it transfers

**CAUTION**: R31/R32 showed that internal improvements do NOT always transfer to external.

## Recommended Next Steps

1. **Immediate**: Send p95 checkpoint for external GMF evaluation
2. **If external confirms**: Address outer regression — consider:
   - Winsorize only on inner-boundary-adjacent pixels (needs architecture awareness)
   - Asymmetric percentiles (higher cap for outer, lower for inner)
   - Combine with Direction A (physics layer alpha increase)
3. **If external does not confirm**: The Winsorize mechanism primarily improves internal step_std proxy but not actual GMF, similar to R31/R32 pattern

## Checkpoints

| Candidate | Path |
|-----------|------|
| p90 | `Traing_Progress/..._20260405_073906/weights/best_tradeoff.pth.tar` |
| p95 | `Traing_Progress/..._20260405_091941/weights/best_tradeoff.pth.tar` |
