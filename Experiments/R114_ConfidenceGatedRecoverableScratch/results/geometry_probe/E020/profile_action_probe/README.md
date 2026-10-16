# R74 E20 Bounded Boundary-Profile Action Probe

Frozen causal upper bound only. No model or training file was changed and no weight was updated.
The intervention can only render a bounded tanh profile from five parameter maps inside a 14 px boundary band.

| family | Full boundary vs Raw | Full+Profile boundary vs Raw | Full IoU delta | Full+Profile IoU delta |
|---|---:|---:|---:|---:|
| asymmetric_blur_halo | -15.286% | -84.861% | 0.003718 | 0.028049 |
| boundary_fade | 1.823% | -88.638% | -0.001160 | 0.174881 |
| low_contrast | 0.299% | -5.711% | -0.000842 | 0.003894 |
| mixed_hard | 0.866% | -91.821% | 0.002608 | 0.106655 |
| uneven_illumination | -0.496% | -44.002% | 0.000868 | 0.134520 |

## Decision

- Repairs all three failed families over Full: **True**
- Preserves halo and uneven illumination: **True**
- Supports adding the action library: **True**

See `analysis_summary.json`, `representative_montage.png`, `tables/`, and `TRAINABLE_HEAD_TARGET_LOSS_DESIGN.md`.
