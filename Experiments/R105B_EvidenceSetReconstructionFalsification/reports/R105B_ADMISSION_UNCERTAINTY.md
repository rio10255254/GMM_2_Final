# R105B Admission and Observation-Jackknife Results

| Output | IoU | Boundary px | Transition center px | MAE gray |
|---|---:|---:|---:|---:|
| valid_multi | 0.97729 | 0.1687 | 0.0783 | 1.794 |
| valid_admission_fallback | 0.97729 | 0.1687 | 0.0783 | 1.864 |
| mismatched_multi_unprotected | 0.02470 | 11.0578 | 9.7034 | 22.797 |
| mismatched_admission_fallback | 0.96952 | 0.2341 | 0.1357 | 3.014 |
| single_fallback_reference | 0.96952 | 0.2341 | 0.1357 | 3.014 |

## Compatibility

```json
{
  "validation_threshold_selection": {
    "threshold": 0.5950251817703247,
    "balanced_accuracy": 1.0,
    "valid_acceptance": 1.0,
    "mismatch_rejection": 1.0
  },
  "test_auc": 1.0,
  "test_valid_acceptance": 0.9930555555555556,
  "test_mismatch_rejection": 1.0,
  "test_valid_score_median": 0.9779049456119537,
  "test_mismatch_score_median": 0.0019441053736954927
}
```

## Uncertainty

```json
{
  "valid_candidate_disagreement": {
    "median_gray": 4.818756077438593,
    "p95_gray": 5.655406203120947,
    "spearman_vs_image_mae": -0.21249095731854356
  },
  "valid_observation_jackknife": {
    "median_gray": 2.6940948609262705,
    "p95_gray": 3.9664063341915607,
    "spearman_vs_image_mae": 0.37242141527349953
  },
  "mismatched_candidate_disagreement": {
    "median_gray": 4.538913443684578,
    "p95_gray": 5.471844892948866,
    "spearman_vs_image_mae": -0.15292982879189776
  },
  "mismatched_observation_jackknife": {
    "median_gray": 26.707816869020462,
    "p95_gray": 34.85360183939338,
    "spearman_vs_image_mae": 0.5839884253677358
  }
}
```

## Decision

```json
{
  "compatibility_generalizes": true,
  "admission_prevents_catastrophic_mismatch": true,
  "jackknife_detects_mismatch": true,
  "jackknife_correlates_on_valid": true
}
```