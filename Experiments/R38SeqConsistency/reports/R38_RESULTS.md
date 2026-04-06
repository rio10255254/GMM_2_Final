# R38 Sequence Consistency Results (2026-04-06)

## Candidate: r38_seq_only
- SEQ_ENABLE=True, 624 pairs (all stages), SEQ_LOSS=0.3, SEQ_GRAD=0.1
- ROBUST_LOSS_PERCENTILE=1.0 (no Winsorize)
- Best epoch: 22

## Result: Step_std improved but sharpness NOT recovered

### Sharpness (0.8px, 20 frames)

| Metric | R30 | R33 hard_p95 | R38 seq_only |
|--------|-----|-------------|-------------|
| Gradient mag | 3.46 | 2.36 (-32%) | **2.26 (-35%)** |
| Laplacian | 1.86 | 0.98 (-47%) | **0.95 (-49%)** |

**R38 is even softer than R33** despite GradMag loss ratio staying at 20-24% (vs R33's 11%).

### Step stability

| Scale | R30 | R33 | R38 |
|-------|-----|-----|-----|
| 8px | 0.199 | 0.174 | **0.136** (best) |
| 0.8px | 0.205 | **0.129** | 0.159 |
| 0.08px | 0.162 | **0.115** | 0.130 |

### 8px quality (R38 strong point)

| Metric | R30 | R33 | R38 |
|--------|-----|-----|-----|
| outer res_std | 2.468 | 3.211 | **2.508** (near R30) |
| inner res_std | 2.719 | 2.970 | **2.453** (best) |
| 8px improvement | 72.8% | 64.7% | **72.5%** (near R30) |

## Root Cause: synthetic labels are softer than R30 output

The sequence delta loss `smooth_l1(pred_delta, lbl_delta)` pushes the model
toward the label's frame-to-frame behavior. Synthetic labels (mathematical
annulus generation) have softer edge profiles than R30's output on real images.
The model learns to match the label's smooth edges → even softer than R33.

The 8px improvement is real because 8px delta is large enough (9% pixel coverage)
to provide strong learning signal. But 0.8px coverage (0.8%) is too weak.

## Conclusion

Sequence consistency training improves 8px macro stability but does NOT
recover sharpness. The synthetic-vs-real domain gap in edge characteristics
means the model learns the wrong sharpness target from labels.

R33 hard_p95 remains the best for 0.8px GMF (external 0.119).
R38 may be useful if 8px macro guard is critical.
