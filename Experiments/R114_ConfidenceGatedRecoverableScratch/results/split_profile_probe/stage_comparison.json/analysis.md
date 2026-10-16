# R114B fixed-stage checkpoint audit

Run: `r114b_split_profile_probe_scratch_20260830`

This is a read-only comparison of E12/E20/E24/E28. Missing stages are skipped. The last checkpoint is never selected automatically.

| Epoch | Stage | Status | MAE | Gain vs base | Identity worst | Tile max | Profile visibility |
|---:|---|---|---:|---:|---:|---:|---:|
| E12 | oracle_geometry | complete | 0.026491013 | 0 | 1.0468434e-06 | 0 | 0 |
| E20 | predicted_geometry | complete | 0.026423044 | 0 | 4.5195494e-07 | 0 | 0 |
| E24 | profile | review_required | 0.027157442 | -0.00073439791 | 0.0052238858 | 0 | 0.34890004 |
| E28 | joint_refinement | review_required | 0.027137675 | -0.0006973116 | 0.00067552268 | 0 | 0.19653283 |

## Findings

- **review**: E24 needs review: identity_below_warning_level, profile_validation_gain_nonnegative
- **review**: E28 needs review: profile_validation_gain_nonnegative
- **policy**: no checkpoint was selected; locked ACM and deployment validation remain required

## Selection policy

No epoch is selected by this audit. A candidate must still pass locked ACM, canonical tiled deployment, real microscopy, and displacement tests.
