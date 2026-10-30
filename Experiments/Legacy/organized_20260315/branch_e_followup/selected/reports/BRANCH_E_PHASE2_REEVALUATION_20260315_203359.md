# BRANCH_E_PHASE2 Reevaluation

- best_0p8_candidate: `be_soft_band`
- control_0p8_center_err: `8.592463`
- best_0p8_center_err: `0.186192`
- center_improvement_abs_px: `8.406270`
- center_improvement_ratio: `97.8331%`
- best_0p8_step_err: `0.580409`
- mid_center_pass: `True`
- mid_step_pass: `False`
- control_guard_step: `0.179484`
- guard_step_limit: `0.299484`
- control_guard_seq_sign: `0.805935`
- guard_seq_sign_floor: `0.755935`
- macro_guard_pass: `True`
- reevaluation_pass: `False`

## Interpretation

Branch E Phase2 does not yet justify launching Round21.
The original absolute 8px <= 0.04 guard is discarded for this harness, but the reevaluation still fails for the reasons below:

- 0.8px step_err remained above 0.45

## Frozen Estimator Policy

- tiny_0p08: `edge_centroid`
- mid_0p8_candidate: `soft_band_refine`
- macro_8px: `edge_band_refine`
- macro_policy_reason: edge_band_refine beat control on 8px benchmark step_err by at least 0.02 with acceptable sign_acc