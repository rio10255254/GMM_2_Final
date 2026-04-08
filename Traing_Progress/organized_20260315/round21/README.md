# round21 — Hybrid Estimator Dead End

## Purpose

`Round21` is the formal follow-up after `branch_e` and `branch_e_followup`. It
tests whether a hybrid estimator plus step-focused training can solve the
mid-step failure mode.

## Start Here

1. `MANIFEST.md`
2. `ROUND21_POSTMORTEM.md`
3. `selected/reports/ROUND21_HYBRID_ESTIMATOR_DECISION_20260315_220621.md`
4. `selected/reports/ROUND21_HYBRID_ESTIMATOR_SUMMARY_20260315_220410.md`
5. `selected/current_round21_hybrid_seed.json`

## Canonical Surface

- Human-readable decision truth: `ROUND21_POSTMORTEM.md`, `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Selected seed: `selected/current_round21_hybrid_seed.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

This round preserves the selected run and audits, but replay still depends on
legacy tools and shared checkpoints outside the directory.
