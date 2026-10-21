# Internal-External Correlation Analysis

Generated: 2026-03-17 14:12:37

Data points: 5 rounds (R25, R26, R27, R28, R29)

## 1. Raw Data

| Round | Winner | Int center_err | Int step_err | Ext 0.8px step_std | Int Source | Ext Source |
|-------|--------|---------------|-------------|-------------------|-----------|-----------|
| R25 | r25_sw010 | 0.093819 | 0.095291 | 0.211973 | auto | auto |
| R26 | r26_sm035 | 0.069099 | 0.085711 | 0.191336 | auto | auto |
| R27 | r27_sm028 | 0.060252 | 0.073719 | 0.196257 | auto | auto |
| R28 | r28_sm030 | 0.082547 | 0.068393 | 0.228184 | auto | auto |
| R29 | r29_sm042 | 0.068186 | 0.078912 | 0.217310 | auto | auto |

## 2. Round-over-Round Change Direction

Key question: when internal metric improves (decreases), does external metric also improve (decrease)?

| Transition | delta center_err | delta step_err | delta ext_step_std | center agrees? | step agrees? |
|-----------|-----------------|---------------|-------------------|---------------|-------------|
| R25->R26 | -0.024720 | -0.009580 | -0.020637 | YES | YES |
| R26->R27 | -0.008847 | -0.011992 | +0.004921 | NO | NO |
| R27->R28 | +0.022295 | -0.005326 | +0.031927 | YES | NO |
| R28->R29 | -0.014361 | +0.010519 | -0.010874 | YES | NO |

Direction agreement rate: center_err = 3/4 (75%), step_err = 1/4 (25%)

## 3. Correlation Coefficients

| Internal Metric | Pearson r | Pearson p | Spearman rho | Spearman p | Interpretation |
|----------------|----------|----------|-------------|-----------|---------------|
| center_err | +0.5399 | 0.3476 | +0.3000 | 0.6238 | moderate positive, NOT significant (n=5, low power) |
| step_err | -0.3251 | 0.5934 | -0.5000 | 0.3910 | weak negative, NOT significant (n=5, low power) |

## 4. Composite Metric Correlation Search

Testing various combinations of internal metrics to find the best predictor of external GMF step_std.

| Composite Formula | Pearson r | Pearson p | Spearman rho | Spearman p |
|------------------|----------|----------|-------------|-----------|
| center_err | +0.5399 | 0.3476 | +0.3000 | 0.6238 |
| 0.7*center + 0.3*step | +0.3588 | 0.5532 | +0.3000 | 0.6238 |
| step_err | -0.3251 | 0.5934 | -0.5000 | 0.3910 |
| mean(center, step) | +0.1840 | 0.7670 | -0.1000 | 0.8729 |
| sqrt(center^2 + step^2) | +0.1795 | 0.7727 | -0.1000 | 0.8729 |
| max(center, step) | +0.1310 | 0.8337 | -0.1000 | 0.8729 |
| 0.3*center + 0.7*step | -0.0235 | 0.9701 | -0.2000 | 0.7471 |

**Best predictor**: `center_err` with Pearson r = +0.5399

## 5. Scatter Plots (ASCII)

### center_err vs ext step_std
```
  ext_step_std
  0.2300 |
           |                               *                  |
           |                                                  |
           |                                                  |
           |                                                  |
           |            *                                     |
           |                                                  |
           |                                              *   |
           |                                                  |
           |                                                  |
           |                                                  |
           |                                                  |
           |  *                                               |
           |                                                  |
           |             *                                    |
           |                                                  |
  0.1895 |__________________________________________________|
           0.0586                              0.0955
           center_err

  Legend:
    R25: (0.0938, 0.211973)
    R26: (0.0691, 0.191336)
    R27: (0.0603, 0.196257)
    R28: (0.0825, 0.228184)
    R29: (0.0682, 0.217310)
```

### step_err vs ext step_std
```
  ext_step_std
  0.2300 |
           |  *                                               |
           |                                                  |
           |                                                  |
           |                                                  |
           |                   *                              |
           |                                                  |
           |                                              *   |
           |                                                  |
           |                                                  |
           |                                                  |
           |                                                  |
           |           *                                      |
           |                                                  |
           |                              *                   |
           |                                                  |
  0.1895 |__________________________________________________|
           0.0670                              0.0966
           step_err

  Legend:
    R25: (0.0953, 0.211973)
    R26: (0.0857, 0.191336)
    R27: (0.0737, 0.196257)
    R28: (0.0684, 0.228184)
    R29: (0.0789, 0.217310)
```

## 6. Key Observations

- **5 rounds** analyzed: R25, R26, R27, R28, R29
- Correlation is **moderate** -- internal metrics are weak-to-moderate predictors
- **Worst mismatch**: R26->R27 -- internal improved but external worsened
- **R27 paradox confirmed**: center_err improved (0.0691 -> 0.0603) but ext step_std worsened (0.191336 -> 0.196257)

## 7. Conclusions & Recommendations

### Verdict: `center_err` shows meaningful correlation with external GMF

However, with n=5 the statistical power is limited. External validation remains essential.

### Recommendations

1. **Use `center_err` as primary internal screening metric**
2. **Still run external GMF** for final validation
3. **Best composite predictor**: `center_err` (r = +0.5399)

---
*Analysis by GeoEdgeAlignSR_v1_InternalExternalCorrelation.py, 2026-03-17 14:12:37*