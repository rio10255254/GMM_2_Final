# round26 — Step Recovery and Baseline Promotion

## Purpose

`Round26` is the step recovery line that promoted `r26_sm035` to the formal
baseline before the later R30 architecture breakthrough.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND26_STEP_RECOVERY_DECISION_20260316_191450.md`
3. `selected/reports/ROUND26_STEP_RECOVERY_SUMMARY_20260316_191318.md`
4. `..\external_compare_r18_r22_r25_r26\README.md`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- External promotion proof: `..\external_compare_r18_r22_r25_r26\reports\EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

Decision and compare artifacts are preserved, but replay still depends on root
tools and historical checkpoints outside this directory.
