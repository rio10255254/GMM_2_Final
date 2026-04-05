# R35 Alpha Boost Results (2026-04-06)

## Candidate: r35_alpha025_p95
- PSF_PHYS_ALPHA_INIT=0.25, ROBUST_LOSS_PERCENTILE=0.95, WARMUP=10
- Best epoch: 38

## Result: FAILED — all metrics regressed

| Metric (0.8px) | R30 | R33 hard_p95 | R35 alpha025 |
|----------------|-----|-------------|--------------|
| step_std_y | 0.205 | **0.129** | 0.229 (+12%) |
| outer res_std | 2.599 | 2.905 | 4.764 (+83%) |
| inner res_std | 2.894 | 2.684 | 4.365 (+51%) |
| 8px step_std | 0.199 | 0.174 | **1.645** |
| gradient mag | 3.46 | 2.36 (-32%) | 2.33 (-33%) |

## Root Cause

Alpha=0.25 makes physics layer too aggressive. Early epochs' strong Wiener
deconvolution introduces artifacts that corrupt encoder feature learning.
Even though alpha is learnable and may settle lower, the damage to early
training is irreversible.

Sharpness did NOT recover (gradient -33%, same as R33). The uniform alpha
increase amplifies all frequencies equally — including noise-prone high
frequencies — causing artifact-dominated residuals.

## Conclusion

Uniform alpha boost does not improve the sharpness-stability trade-off.
The physics layer needs **frequency-selective** control (R37 hypothesis),
not a uniform strength increase.
