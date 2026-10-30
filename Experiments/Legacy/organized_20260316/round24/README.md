# round24 — Single-Frame Abs-Center Diagnostic

## Purpose

`Round24` is the single-frame abs-center fine-tune diagnostic branch in the
`organized_20260316` legacy mainline batch.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND24_SINGLE_ABS_DECISION_20260316_163357.md`
3. `selected/reports/ROUND24_SINGLE_ABS_SUMMARY_20260316_163227.md`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- Runtime/artifact payloads: `selected/runs/`, `archive/`, `pending/`

## Replay Support

`historical-only`

This directory preserves the decision chain and run outputs, but it does not
provide a self-contained replay contract.
