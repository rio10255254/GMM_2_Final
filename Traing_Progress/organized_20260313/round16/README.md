# round16 — EDGEFIT Mainline Shift

## Purpose

`Round16` is the first legacy round in this batch. It introduced the
`edge_centroid` estimator line that displaced the earlier algebraic-fit
baseline as the preferred direction for later rounds.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND16_EDGEFIT_MULTISCALE_SUMMARY_20260312_090623.md`
3. `selected/reports/ROUND16_EDGEFIT_CHECKPOINT_AUDIT_SUMMARY_20260312_090623.md`
4. `selected/current_edgefit_seed.json`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Selected seed: `selected/current_edgefit_seed.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

The selected run, audit reports, and seed are preserved, but replay still
depends on legacy training/runtime tooling outside this directory.
