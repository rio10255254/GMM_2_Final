# round29 — Step-Mag Upper Sweep Falsification

## Purpose

`Round29` is the `step_mag > 0.35` upper sweep branch that passed internal gates
but failed to beat the existing external optimum.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND29_STEP_MAG_UPPER_DECISION_20260317_124715.md`
3. `selected/reports/ROUND29_STEP_MAG_UPPER_SUMMARY_20260317_115029.md`
4. `..\external_compare_r18_r22_r25_r26_r27_r28_r29\README.md`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- External falsification proof: `..\external_compare_r18_r22_r25_r26_r27_r28_r29\reports\EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.md`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

Decision and compare artifacts are preserved, but replay still depends on root
tools and historical checkpoints outside this directory.
