# R105B Evidence Controls

| Control | IoU | Boundary px | Transition center px | Width px | MAE gray |
|---|---:|---:|---:|---:|---:|
| raw_single | 0.94037 | 0.3647 | 0.4299 | 0.6603 | 7.853 |
| raw_mean_four | 0.96083 | 0.2350 | 0.2833 | 0.4502 | 3.815 |
| raw_oracle_frame | 0.96579 | 0.2521 | 0.1785 | 0.4833 | 3.967 |
| matched_point_four_diagnostic | 0.97390 | 0.1907 | 0.1042 | 0.3899 | 2.627 |
| evidence_four_duplicate_first | 0.96783 | 0.2496 | 0.1354 | 0.3372 | 3.455 |
| evidence_four_diverse | 0.97729 | 0.1687 | 0.0783 | 0.2064 | 1.794 |
| evidence_four_mismatched | 0.02470 | 11.0578 | 9.7034 | 5.2752 | 22.797 |

## Uncertainty

```json
{
  "diverse": {
    "median_gray": 4.818756077438593,
    "p95_gray": 5.655406203120947,
    "spearman_vs_image_mae": -0.21249095731854356
  },
  "duplicate_first": {
    "median_gray": 5.335264261811972,
    "p95_gray": 6.542363301850855,
    "spearman_vs_image_mae": -0.07283176593521422
  },
  "mismatched": {
    "median_gray": 4.538913443684578,
    "p95_gray": 5.471844892948866,
    "spearman_vs_image_mae": -0.15292982879189776
  }
}
```

## Decision

```json
{
  "new_observations_beat_repeated_frame": {
    "boundary": true,
    "transition_center": true,
    "image_mae": true
  },
  "model_beats_simple_average": {
    "boundary": true,
    "transition_center": true,
    "image_mae": true
  },
  "uncertainty_detects_mismatch": false
}
```