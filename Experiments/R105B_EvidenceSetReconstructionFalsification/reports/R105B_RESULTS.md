# R105B Evidence-Set Reconstruction Results

Status: complete

| Arm | IoU | Boundary px | Centroid px | Transition center px | Width px | MAE gray | Identity gray |
|---|---:|---:|---:|---:|---:|---:|---:|
| matched_point_single | 0.95773 | 0.2799 | 0.1197 | 0.2314 | 0.4968 | 4.727 | 0.534 |
| evidence_set_single | 0.96952 | 0.2341 | 0.1180 | 0.1357 | 0.3044 | 3.014 | 0.265 |
| evidence_set_four | 0.97729 | 0.1687 | 0.0748 | 0.0783 | 0.2064 | 1.794 | 0.291 |
| evidence_set_four_physics_candidate | 0.97277 | 0.1741 | 0.0876 | 0.1266 | 0.3513 | 2.087 | 0.607 |
| evidence_set_four_oracle_candidate | 0.97277 | 0.1741 | 0.0892 | 0.1266 | 0.3513 | 2.087 | 0.607 |

## Uncertainty

```json
{
  "evidence_set_single": {
    "median_uncertainty_gray": 5.798726342618465,
    "p95_uncertainty_gray": 7.530219497624782,
    "spearman_uncertainty_vs_image_mae": 0.1872598665702114,
    "spearman_uncertainty_vs_boundary_distance": 0.4569005706936741
  },
  "evidence_set_four": {
    "median_uncertainty_gray": 4.818765101954341,
    "p95_uncertainty_gray": 5.655405775643885,
    "spearman_uncertainty_vs_image_mae": -0.21249095731854356,
    "spearman_uncertainty_vs_boundary_distance": 0.10515633791495861
  }
}
```

## Motion, exposure and tile

```json
{
  "motion_exposure": {
    "matched_point_single": {
      "known_motion_error_px_median": 0.08548766981641402,
      "known_motion_error_px_p95": 0.23090160240562166,
      "exposure_center_spread_px_median": 0.041390910714342075,
      "exposure_center_spread_px_p95": 11.09200318609252
    },
    "evidence_set_single": {
      "known_motion_error_px_median": 0.10546816843697931,
      "known_motion_error_px_p95": 0.3684373461207195,
      "exposure_center_spread_px_median": 0.08260549094650878,
      "exposure_center_spread_px_p95": 3.305422042227895
    },
    "evidence_set_four": {
      "known_motion_error_px_median": 0.0788387717059379,
      "known_motion_error_px_p95": 0.19037924100910616,
      "exposure_center_spread_px_median": 0.07153421171696364,
      "exposure_center_spread_px_p95": 2.419435133567181
    }
  },
  "tile": {
    "matched_point_single": {
      "max_abs_gray": 7.599592208862305e-05,
      "max_mean_abs_gray": 6.292587841016939e-06
    },
    "evidence_set_single": {
      "max_abs_gray": 6.079673767089844e-05,
      "max_mean_abs_gray": 6.321448836388299e-06
    },
    "evidence_set_four": {
      "max_abs_gray": 6.079673767089844e-05,
      "max_mean_abs_gray": 7.163374448282411e-06
    }
  }
}
```

## Decision

The mechanism did not yet demonstrate a reliable held-out advantage; do not start a full model.

This is a procedural mechanism probe. It does not establish real SEM or external-GMF improvement.