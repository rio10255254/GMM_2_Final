# R105A Geometry Renderer Falsification Results

Status: complete

## Matched held-out geometry results

| Arm | IoU | Boundary distance px | Centroid error px | Transition-center error px | Width error px | Halo fraction | Identity MAE gray |
|---|---:|---:|---:|---:|---:|---:|---:|
| oracle_renderer | 0.99701 | 0.0352 | 0.0339 | 0.0145 | 0.2326 | 0.01556 | 0.012 |
| learned_sdf_true_width_true_levels | 0.89492 | 1.1569 | 0.4631 | 0.6346 | 0.6291 | 0.01215 | 0.976 |
| learned_sdf_learned_width_true_levels | 0.89492 | 1.1569 | 0.4631 | 0.6167 | 0.6287 | 0.01215 | 1.054 |
| full_learned_renderer | 0.96204 | 0.4609 | 0.1925 | 0.1462 | 0.3944 | 0.01361 | 0.580 |
| matched_residual | 0.97534 | 0.2936 | 0.1248 | 0.0373 | 0.5051 | 0.02029 | 0.135 |

## Motion, exposure and tile checks

| Arm | Motion median px | Motion p95 px | Exposure center spread px | Full/tiled max gray |
|---|---:|---:|---:|---:|
| matched_residual | 0.0942 | 0.2989 | 0.0153 | 0.000889 |
| full_learned_renderer | 0.0793 | 0.2346 | 0.0651 | 0.006688 |

## Decision

Actionable renderer did not consistently dominate the matched residual arm; do not start a full R105.

Core directions won: 2 / 5

This is a procedural mechanism probe. It does not establish real SEM or external-GMF improvement.