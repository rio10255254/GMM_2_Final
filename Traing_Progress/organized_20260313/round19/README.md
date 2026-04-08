# round19 — ABSANCHOR Falsification Round

## Purpose

`Round19` tests whether direct absolute-center anchoring can break the
`0.8px center_err` plateau that remained after `Round18`.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND19_ABSANCHOR_MULTISCALE_SUMMARY_20260313_190541.md`
3. `selected/reports/ROUND19_ABSANCHOR_CHECKPOINT_AUDIT_SUMMARY_20260313_190541.md`
4. `selected/current_absanchor_seed.json`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Selected seed: `selected/current_absanchor_seed.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

The selected run and reports are preserved, but this surface should be treated
as a historical falsification round rather than a turnkey replay package.
