# round18 — CENTERPUSH Adopted Legacy Baseline

## Purpose

`Round18` is the `CENTERPUSH` round that became the adopted internal baseline
for the pre-external-compare era. It pushes center-focused weighting on top of
the `Round17` line.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND18_CENTERPUSH_MULTISCALE_SUMMARY_20260313_142259.md`
3. `selected/reports/ROUND18_CENTERPUSH_CHECKPOINT_AUDIT_SUMMARY_20260313_142259.md`
4. `selected/current_centerpush_seed.json`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Selected seed: `selected/current_centerpush_seed.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`, `external_validation/`

## Replay Support

`partial`

The selected run, reports, and external-validation payloads are preserved, but
replay still depends on root tools and historical checkpoints outside this
directory alone.
