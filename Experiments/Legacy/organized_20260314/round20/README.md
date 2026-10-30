# round20 — Process Probe Round

## Purpose

`Round20` is a process-validation round. It tests whether the `Round19`
plateau was caused by epoch-0 baseline locking rather than by the model
mechanism itself.

## Start Here

1. `MANIFEST.md`
2. `ROUND20_POSTMORTEM.md`
3. `selected/reports/ROUND20_PROCESS_PROBE_SUMMARY_20260314_205446.md`
4. `selected/reports/ROUND20_PROCESS_PROBE_AUDIT_SUMMARY_20260314_205446.md`
5. `selected/current_process_probe_seed.json`

## Canonical Surface

- Human-readable decision truth: `ROUND20_POSTMORTEM.md`, `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Selected seed: `selected/current_process_probe_seed.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`partial`

The probe outputs are preserved, but this round depends on the broader legacy
training/runtime harness and should not be treated as self-contained.
