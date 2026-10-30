# pairwise_delta_probe — Side Probe Surface

## Purpose

This probe tests whether pairwise-delta estimation plus single-frame absolute
anchoring can rescue the center-stability plateau without breaking the macro
guard.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/PAIRWISE_DELTA_PROBE_SUMMARY_20260315_224024.md`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Runtime/artifact payloads: `archive/`

## Replay Support

`partial`

The selected probe reports are preserved, but replay still depends on the
legacy process-probe harness and external tooling.
