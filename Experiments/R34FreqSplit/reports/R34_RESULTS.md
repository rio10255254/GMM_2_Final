# R34 Frequency-Split Results (2026-04-05)

## Candidate: r34_freq_s15_p95
- ROBUST_FREQ_SPLIT=True, SIGMA=1.5, P95, W_LO=0.5, W_HI=0.5
- Best epoch: 38

## Result: NO IMPROVEMENT over R33

### Step stability

| Scale | R30 | R33 hard_p95 | R34 freq-split |
|-------|-----|-------------|----------------|
| 0.8px | 0.205 | **0.129** | 0.141 |
| 0.08px | 0.162 | **0.115** | 0.115 |
| 8px | 0.199 | 0.174 | **0.370** (regression) |

### Visual sharpness (identical to R33)

| Metric | R30 | R33 | R34 |
|--------|-----|-----|-----|
| Gradient magnitude | 3.46 | 2.36 (-32%) | 2.36 (-32%) |
| Laplacian | 1.86 | 0.98 (-47%) | 0.99 (-47%) |

### Root cause

Gaussian blur at σ=1.5 on 256×256 patches produces lo/hi components whose Sobel
gradients are highly correlated. The un-capped hi-freq loss did not recover sharpness
because hi-freq gradients at defect angles are still large — the model suppresses them
anyway to minimize total loss. The freq-split adds no signal the model can exploit.

The 8px regression (-86%) suggests the frequency decomposition disrupts the balance
for larger-scale images (1520×2180) where the annulus geometry occupies different
spatial frequencies.

## Conclusion

Frequency-split at the spatial domain (Gaussian blur) does not break the sharpness-stability
trade-off. The trade-off is fundamental to gradient-based optimization with Winsorize:
suppressing outlier gradients inherently reduces sharpness.

R33 hard_p95 remains the best variant across all experiments (R33 + R34).
