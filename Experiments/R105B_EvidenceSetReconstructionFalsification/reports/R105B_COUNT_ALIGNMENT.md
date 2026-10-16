# R105B Observation Count and Alignment Tolerance

## Observation count

| Mode | IoU | Boundary px | Transition center px | MAE gray |
|---|---:|---:|---:|---:|
| evidence_n1 | 0.96952 | 0.2341 | 0.1357 | 3.014 |
| evidence_n2 | 0.97354 | 0.1983 | 0.1076 | 2.283 |
| evidence_n4 | 0.97729 | 0.1687 | 0.0783 | 1.794 |

## Residual alignment error

| Error | IoU | Boundary px | Transition center px | MAE gray | Accepted |
|---|---:|---:|---:|---:|---:|
| residual_alignment_0.00px | 0.97729 | 0.1687 | 0.0783 | 1.794 | 0.993 |
| residual_alignment_0.15px | 0.97631 | 0.1750 | 0.0790 | 1.796 | 0.993 |
| residual_alignment_0.30px | 0.97596 | 0.1789 | 0.0789 | 1.794 | 0.993 |
| residual_alignment_0.50px | 0.97476 | 0.1917 | 0.0858 | 1.800 | 0.993 |
| residual_alignment_0.75px | 0.97282 | 0.2043 | 0.0932 | 1.834 | 0.993 |
| residual_alignment_1.00px | 0.96977 | 0.2268 | 0.1133 | 1.894 | 0.993 |
| residual_alignment_1.50px | 0.96567 | 0.2800 | 0.1328 | 2.003 | 0.993 |

## Decision

```json
{
  "best_observation_count": 4,
  "largest_tested_alignment_error_still_better_than_single_px": 1.0
}
```