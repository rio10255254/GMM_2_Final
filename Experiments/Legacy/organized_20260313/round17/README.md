# round17 — STEPFIX Recovery Round

## Purpose

`Round17` extends the `edge_centroid` line by directly repairing step
magnitude behavior. It established the clean `0.8px` internal baseline used by
later center-focused rounds.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND17_STEPFIX_MULTISCALE_SUMMARY_20260313_130618.md`
3. `selected/reports/ROUND17_STEPFIX_CHECKPOINT_AUDIT_SUMMARY_20260313_130618.md`
4. `selected/current_stepfix_seed.json`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Selected seed: `selected/current_stepfix_seed.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

The selected run and audit outputs are preserved, but replay still depends on
legacy tooling and shared model code outside this directory.
