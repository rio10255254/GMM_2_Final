# R128 final execution and result audit

Assessment: execution and comparison numbers are verified and shareable with the stated reference limitations. Production adoption is not supported. The four runs completed at2026-09-09T13:55:38UTC; the final review was performed after completion.

## Execution

analysis/final_review/audit_execution.py independently reconciles all four final model/optimizer states, complete ledgers, repeated-update equivalence, declared scene/noise/order, learning-rate schedule, weighted objective arithmetic, all scheduled evaluations, all768data archives/metadata and5,403historical protected files.

There are32,768unique optimizer steps and224exactly repeated recovery calls, giving32,992actual calls in the full-training ledgers. Engineering diagnostics remain separate. All four arms/seeds consumed identical recorded input bytes and orders for each logical step.64independently regenerated consumed-photo checks cover all16passes. Maximum relative difference between independently summed logged loss components and recorded float32loss is1.6766045947116666e-7.480files in the12trained real evaluations were checked against original identities. Original frozen study and recovery identities were not replaced.

The result is saved at results/final_review/execution_audit.json, including final checkpoint/completion references, counts and the executed audit-source identity.

## Comparison

analysis/final_review/compare_results.py recomputes all288final SEM rows from original source images and saved full outputs. It verifies common source/SEM-only ray populations, retained invalid-candidate counts and reference-band extrema using an independent sampled/breakpoint calculation. Maximum difference from saved SEM values is9.94e-17. This is native diameter/center-pitch comparison under operational SEM inner/rim/outer definitions, not material-edge truth or physical instrument calibration.

| Run | SEM improved / worsened / unavailable, of72 | Normal improved, of36 | Dark improved / worsened, of36 | Worst motion change vs Raw, px | Generated-test MAE, gray |
|---|---:|---:|---:|---:|---:|
| I_s1285001 |31 /41 /0|31|0 /36|0.004660|1.528832|
| P_s1285001 |30 /37 /5|29|1 /35|0.005856|1.567921|
| I_s1285002 |40 /31 /1|34|6 /30|0.005946|1.617638|
| P_s1285002 |43 /29 /0|36|7 /29|0.005860|1.543970|

All models worsen all16fully-neural dark-exposure objects under the declared readout. The20boundary-influenced objects/exposure remain included and separately labeled; their Raw retention must not be interpreted as learned restoration. Reference sensitivity at30/50/70percent contrast is retained in the complete CSV. Invalid objects are not omitted from the72-object denominator.

All24final model/motion pairs pass the existing source-relative consistency criterion. The retained candidate's worst pair,50x_0p5um, was independently remeasured at0.005860166654473166px change versus Raw. No independent stage position is available. Fresh GPU inference of the entire dark SEM-paired optical image with P_s1285002 reproduces both guarded and unguarded saved output bitwise.

Raw generated-test MAE is4.294058gray. The candidates improve the mean on synthetic scenes, but modify all6clean controls and have worst-case generated scene/pixel failures; this cannot establish real metrological superiority. Same-material SEM/optical edge correspondence remains unqualified.

## Decision scope

Retain P_s1285002 at the predeclared step8192as the single candidate for further repair. It has complete72-object coverage and the strongest normal-exposure improvement in this set. Its29dark regressions and all16dark-interior regressions prevent a reliable-measurement deployment claim. This is explicitly post-training engineering prioritization, not an invented preregistered promotion threshold, evidence that the P objective is consistently causally superior, or selection on an unseen real holdout.

No candidate is selected for production; COMBO remains the formal baseline. The eventual deliverable is one supported application model, with selection performed by the assistant. No new training was launched by this review.

## Reproducible artifacts

- results/final_review/execution_audit.json
- results/final_review/comparison_verification.json
- results/final_review/all_final_SEM_rows.csv
- results/final_review/comparison.csv
- results/final_review/selection.json
- results/final_review/chart_contract.json
- analysis/final_review/audit_execution.py
- analysis/final_review/compare_results.py

Figures were inspected as exported PNGs. Counts, directions, count axes starting at zero, model ordering, fixed per-exposure display scales and full failure populations are visible. Historical reports and frozen training/evaluation outputs remain intact. Earlier current-state text is preserved under analysis/final_review/context_before_closeout.
