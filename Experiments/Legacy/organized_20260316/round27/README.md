# round27 — Step-Mag Recovery Frontier

## Purpose

`Round27` is the post-R26 recovery frontier that improved internally but did not
replace `R26` on the external main battlefield.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND27_STEP_MAG_RECOVERY_DECISION_20260316_204452.md`
3. `selected/reports/ROUND27_STEP_MAG_RECOVERY_SUMMARY_20260316_204323.md`
4. `..\external_compare_r18_r22_r25_r26_r27\README.md`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- External no-upgrade proof: `..\external_compare_r18_r22_r25_r26_r27\reports\EXTERNAL_COMPARE_R18_R22_R25_R26_R27_SUMMARY.md`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

Decision and compare artifacts are preserved, but replay still depends on root
tools and historical checkpoints outside this directory.
