# round22 — Pairmix Legacy Baseline

## Purpose

`Round22` is the formal validation round for the `pairmix_algblend` line that
emerged from `pairwise_delta_probe`. It became the legacy baseline later used
in the `external_compare_round18_round22` tie-break.

## Start Here

1. `MANIFEST.md`
2. `ROUND22_POSTMORTEM.md`
3. `selected/reports/ROUND22_PAIRMIX_HYBRID_DECISION_20260315_230456.md`
4. `selected/reports/ROUND22_PAIRMIX_HYBRID_SUMMARY_20260315_230314.md`
5. `selected/current_round22_pairmix_seed.json`

## Canonical Surface

- Human-readable decision truth: `ROUND22_POSTMORTEM.md`, `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Selected seed: `selected/current_round22_pairmix_seed.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

The selected run, postmortem, and audit outputs are preserved, but replay still
depends on shared legacy tooling outside this directory.
