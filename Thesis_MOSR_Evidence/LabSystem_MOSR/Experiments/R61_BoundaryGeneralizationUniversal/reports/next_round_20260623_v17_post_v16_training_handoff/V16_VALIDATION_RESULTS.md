# v16 Validation Results

## Verdict

v16 is not promotable as the thesis result.

It is not useless: it slightly improves the simulated boundary overall mean and fixes several v14 boundary failure groups. But the final gate still fails because the small-bias boundary groups remain worse than R39, 20260603 real-motion stability is worse than raw input and slightly worse than v14, and Step selected-motion stability is slightly worse than R39 and v14.

## Candidate

`r61_motion_texture_stepguard_v16_dualgate_boundary_focus`

Best checkpoint:

`Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020/weights/best_tradeoff.pth.tar`

## A. Simulated Boundary Validation

Matched v14 settings:

- 96 cases.
- seeds 7001, 7002, 7003, 7004.
- biases 0.0, 0.5, 1.0, 1.5, 2.0, 2.5.
- blur sigmas 1.0 and 1.5.
- noise sigmas 1.0 and 3.0.

Output folder:

`R61_stepguard_v16_dpv96_matched_20260623/diverse_phantom_validation_20260623_220416`

Readable summary:

`R61_stepguard_v16_dpv96_matched_20260623/diverse_phantom_validation_20260623_220416/BOUNDARY_GATE_SUMMARY.md`

Key result:

| comparison | baseline mean px | v16 mean px | pass |
|---|---:|---:|---|
| vs R39 | 0.483704669 | 0.482734433 | false |
| vs R8 | 0.484760639 | 0.482734433 | false |
| vs v14 | 0.483153311 | 0.482734433 | false |

What improved:

- Overall mean improved versus R39, R8, and v14.
- v14's bright-boundary failure is no longer a failure versus R39.
- v14's annulus and ellipse failures are no longer failures versus R39.

What still failed:

- 0.0 px bias group is still worse than R39.
- 0.5 px bias group is still worse than R39.

## B. 20260603 Real Sequence

v16 reconstruction case:

`Reconstruct_Progress/20260603_external_gmf_prepare/24_r61_motion_texture_stepguard_v16_full_e8_best`

Motion summary:

`Reconstruct_Progress/20260603_external_gmf_prepare/local_motion_probe_summary_after_r61_stepguard_v16_full_e8.md`

Key tail std dy:

| case | tail std dy px |
|---|---:|
| raw input | 0.268818 |
| R39 a970 candidate | 0.278475 |
| v14 motion texture | 0.276390 |
| v16 Step guard | 0.276528 |

Result:

v16 is better than R39, but slightly worse than v14 and still worse than raw input. This layer fails the v15 target rule.

## C. Step Selected Position-10 Center-Crop Sequence

Source check:

- original Step folder has 788 BMP files.
- selected sequence has 40 positions.
- selected positions run from 0 to 390.
- both replicate streams were checked.
- clean recopy audit later found the earlier raw 0.74 px result came from a weak intensity-based measurement. Edge-based raw measurement gives about 8 px, so the selected position-10 sequence is consistent with the expected 1 um scale.

v16 Step reconstruction case:

`Step_analysis_20260623/r61_step_1um_center2048_recon_package/03_v16_stepguard_step_1um_center2048`

Step motion summary:

`Step_analysis_20260623/STEP_MOTION_PROBE_CENTER2048_RAW_R39_V14_V16_SUMMARY.md`

Preview:

`Step_analysis_20260623/step_center2048_raw_r39_v14_v16_preview.png`

Key Step values:

| case | repeat median mag px | step median dx px | step std dx px |
|---|---:|---:|---:|
| raw | 0.019576 | 0.742537 | 0.061380 |
| R39 | 0.134328 | 8.024669 | 0.097845 |
| v14 | 0.133604 | 8.026425 | 0.097870 |
| v16 | 0.133817 | 8.025998 | 0.097913 |

Result:

v16 preserves the reconstructed Step scale near 8 px. A clean recopy audit found that the earlier raw 0.743 px result came from intensity-based phase correlation with weak response. When the same raw images are measured with edge-based phase correlation, raw also gives about 8 px. So this is not evidence that the model physically amplifies displacement by 10x.

The remaining concern is stability, not scale. On the Step metric used here, v16 is still slightly worse than R39 and v14.

Clean recopy audit:

`Step_analysis_20260623/clean_step_audit_from_original_pos10_20260623_2218/STEP_CLEAN_RECOPY_AUDIT_REPORT.md`

Replicate-stream check:

| case | replicate | step std dx px | step median dx px | step median mag px |
|---|---:|---:|---:|---:|
| R39 | 0 | 0.093835 | 8.032255 | 8.032277 |
| R39 | 1 | 0.101694 | 8.017949 | 8.018117 |
| v14 | 0 | 0.093793 | 8.033546 | 8.033723 |
| v14 | 1 | 0.101779 | 8.017045 | 8.017198 |
| v16 | 0 | 0.093731 | 8.032855 | 8.033033 |
| v16 | 1 | 0.101918 | 8.016795 | 8.016963 |

Replicate 0 is close to v14/R39, but replicate 1 is slightly worse. This supports the same conclusion as the combined Step gate: v16 did not improve Step stability.

## D. Triple Gate

Output:

`Step_analysis_20260623/triple_gate_v16_boundary_real_step_vs_raw_r39.json`

Result:

| gate | pass |
|---|---|
| boundary | false |
| 20260603 real motion | false |
| Step | false |
| overall | false |

Specific failures:

- Boundary: 0.0 px and 0.5 px small-bias groups remain worse than R39.
- 20260603: v16 tail std dy is 0.007709 px worse than raw input.
- Step: v16 step std dx is 0.0000679 px worse than R39.

## Next Design Direction

Do not discard v16. Use it as evidence that the Step-like guard helped some boundary groups but did not solve displacement stability.

Next candidate should not increase general sharpness pressure. It should target:

- 0.0 px and 0.5 px small-bias boundary invariance.
- Motion stability without forcing the Step reconstruction to overfit the current target sample.
- A guard that protects 20260603 tail stability against raw input, not only against R39.

Do not use per-sample calibration or posthoc correction.

## Process Cleanup

After validation, no persistent Python or conda process was left running.
