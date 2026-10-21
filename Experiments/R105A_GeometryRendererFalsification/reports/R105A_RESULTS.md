# R105A Geometry Renderer Falsification Results

Status: complete

## Matched held-out geometry results

| Arm | IoU | Boundary distance px | Centroid error px | Transition-center error px | Width error px | Halo fraction | Identity MAE gray |
|---|---:|---:|---:|---:|---:|---:|---:|
| oracle_renderer | 0.99701 | 0.0352 | 0.0339 | 0.0145 | 0.2326 | 0.01556 | 0.012 |
| learned_sdf_true_width_true_levels | 0.90585 | 0.9720 | 0.2831 | 0.2983 | 0.4129 | 0.01349 | 0.707 |
| learned_sdf_learned_width_true_levels | 0.90650 | 0.9720 | 0.2831 | 0.2942 | 0.4035 | 0.01349 | 0.751 |
| full_learned_renderer | 0.97042 | 0.3307 | 0.1389 | 0.3204 | 0.3117 | 0.01859 | 0.553 |
| matched_residual | 0.97668 | 0.2657 | 0.1219 | 0.0868 | 0.3830 | 0.02109 | 0.257 |

## Motion, exposure and tile checks

| Arm | Motion median px | Motion p95 px | Exposure center spread px | Full/tiled max gray |
|---|---:|---:|---:|---:|
| matched_residual | 0.0640 | 0.3553 | 0.0295 | 0.012357 |
| full_learned_renderer | 0.0744 | 0.2062 | 0.0521 | 0.016765 |

## Decision

Actionable renderer did not consistently dominate the matched residual arm; do not start a full R105.

Core directions won: 2 / 5

This is a procedural mechanism probe. It does not establish real SEM or external-GMF improvement.