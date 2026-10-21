# R119 controlled boundary factors

Canonical report: ../../reports/R119_CONTROLLED_BOUNDARY_FACTORS.md

Scope: 240 primary factorial conditions, 100 separately declared intensity follow-ups, and 432 existing real SEM-linked observations. Frozen E42 only. No training, model selection, or confirmation evaluation.

The primary protocol was recorded before execution. Subsequent intensity and real-profile protocols are explicitly post-primary diagnostic follow-ups. Model outputs in synthetic cases are float arrays, including the noisy-uint8 INPUT condition. True object motion moves its reference too.

All 2,720 image arrays were checked finite, bounded and correctly shaped. Twenty-four repeated baseline-control pairs reproduce exactly. Seven-path profile summaries were recomputed; alternative interpolation reproduced selected profiles within 0.000002 pixels. Invalid real profiles remain recorded and common comparisons retain at least 711/720. Ninety-three protected historical inputs remain unchanged.

The initial real-profile calibration failure and generic finite-check mistake are retained and described in the report and verification.json. New v2 sampling coordinates use only the SEM-mask reference, never optical observations, and satisfy a stricter calibration bound. This does not establish physical equality of optical and SEM edges.

Decision: prioritize optical/SEM reference correspondence and independent brightness/contrast observation coverage before architecture or loss-weight changes. Retain position capability; no fixed shrink correction and no long training launch. The unique physical cause of the reference discrepancy is unresolved.

New numerical records and image/profile arrays are under cases/, radiometry_cases/, real_profiles_v2/. Earlier empty real_profiles/ is the preserved initial attempt. All original protocols, code and execution records remain available.
