# R105A Geometry Renderer Falsification Results

Status: complete

## Matched held-out geometry results

| Arm | IoU | Boundary distance px | Centroid error px | Transition-center error px | Width error px | Halo fraction | Identity MAE gray |
|---|---:|---:|---:|---:|---:|---:|---:|
| oracle_renderer | 1.00000 | 0.0000 | 0.0000 | 0.0156 | 0.2446 | 0.01569 | 0.000 |
| learned_sdf_true_width_true_levels | 0.88594 | 1.2765 | 0.3602 | 0.6759 | 0.6134 | 0.01358 | 1.023 |
| learned_sdf_learned_width_true_levels | 0.88594 | 1.2765 | 0.3602 | 0.6890 | 0.6532 | 0.01358 | 1.082 |
| full_learned_renderer | 0.96300 | 0.4252 | 0.1501 | 0.3818 | 0.4009 | 0.01944 | 0.828 |
| matched_residual | 0.97869 | 0.2557 | 0.0869 | 0.0424 | 0.5681 | 0.02112 | 0.052 |

## Motion, exposure and tile checks

| Arm | Motion median px | Motion p95 px | Exposure center spread px | Full/tiled max gray |
|---|---:|---:|---:|---:|
| matched_residual | 0.0926 | 0.3159 | 0.0129 | 0.000517 |
| full_learned_renderer | 0.0550 | 0.1557 | 0.0903 | 0.005753 |

## Decision

Actionable renderer did not consistently dominate the matched residual arm; do not start a full R105.

Core directions won: 2 / 5

This is a procedural mechanism probe. It does not establish real SEM or external-GMF improvement.