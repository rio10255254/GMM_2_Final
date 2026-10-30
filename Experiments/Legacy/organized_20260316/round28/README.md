# round28 — Step-Mag Downsweep Falsification

## Purpose

`Round28` is the `step_mag < 0.35` downsweep branch that was formally falsified
by external compare.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND28_STEP_MAG_BALANCE_DECISION_20260316_225523.md`
3. `selected/reports/ROUND28_STEP_MAG_BALANCE_SUMMARY_20260316_225344.md`
4. `..\external_compare_r18_r22_r25_r26_r27_r28\README.md`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- External falsification proof: `..\external_compare_r18_r22_r25_r26_r27_r28\reports\EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_SUMMARY.md`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

Decision and compare artifacts are preserved, but replay still depends on root
tools and historical checkpoints outside this directory.
