# R74 E20 Oracle / Local-Reliability Gate Probe

This is a frozen-model causal upper bound, not a deployable model and not training.
Synthetic truth is used only to decide where an already-learned shift or width action is locally reliable.
The gate rule was fixed before locked ACM and was not tuned from ACM results.

| family | Full boundary change | Separate-oracle boundary change | Full IoU delta | Separate-oracle IoU delta |
|---|---:|---:|---:|---:|
| asymmetric_blur_halo | -15.286% | -14.956% | 0.003718 | 0.003632 |
| boundary_fade | 1.823% | 1.511% | -0.001160 | -0.000980 |
| low_contrast | 0.299% | 0.478% | -0.000842 | -0.000488 |
| mixed_hard | 0.866% | 2.901% | 0.002608 | 0.000333 |
| uneven_illumination | -0.496% | -0.452% | 0.000868 | 0.001093 |

## Per-image selector upper bound

This supplementary bound chooses the lower boundary error after seeing truth. It asks whether the existing action library contains a repair at all.

| family | Best of Raw/Full | Best of Raw/all observed methods |
|---|---:|---:|
| asymmetric_blur_halo | -15.286% | -15.395% |
| boundary_fade | -0.451% | -0.698% |
| low_contrast | 0.000% | -0.015% |
| mixed_hard | -0.198% | -0.198% |
| uneven_illumination | -0.496% | -0.547% |

## Decision

Supports learning separate gates: **False**

See `analysis_summary.json` and `tables/` for the complete locked results.
