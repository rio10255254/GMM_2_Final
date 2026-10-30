# TTA Experiment: R26 Baseline vs R26 + TTA (cross5)

## Step Std Comparison
| Scale | R26 Baseline | R26 + TTA | Delta | Improvement % |
| --- | ---: | ---: | ---: | ---: |
| 8px (pitch1um) | 0.201031 | 0.200948 | -0.000083 | +0.0% |
| 0.8px (pitch0p1um) | 0.191336 | 0.214034 | +0.022698 | -11.9% |
| 0.08px (pitch0p01um) | 0.180313 | 0.153058 | -0.027255 | +15.1% |

## Lag-1 Autocorrelation
| Scale | R26 Baseline | R26 + TTA | Delta |
| --- | ---: | ---: | ---: |
| 8px (pitch1um) | 0.083233 | 0.143517 | +0.060284 |
| 0.8px (pitch0p1um) | 0.225886 | 0.112999 | -0.112887 |
| 0.08px (pitch0p01um) | -0.010205 | -0.106042 | -0.095837 |

## Verdict
- Main battlefield (0.8px): baseline=0.191336, TTA=0.214034
- Improvement: -11.9%
- TTA does NOT outperform baseline
- TTA lag-1 autocorr: 0.112999 (threshold > 0.1)
- Autocorrelation check: PASS

### Conclusion: TTA is NOT effective
The equivariance-sharpness conflict hypothesis may be incorrect.
Re-examine the root cause analysis before proceeding with B1.

## Outlier Summary (0.8px)
| Model | Removed | Raw step_std | Filtered step_std |
| --- | ---: | ---: | ---: |
| r26_baseline | 0 | 0.191336 | 0.191336 |
| r26_tta_cross5 | 0 | 0.214034 | 0.214034 |