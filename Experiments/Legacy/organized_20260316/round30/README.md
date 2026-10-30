# round30 — Architecture Breakthrough

## Purpose

`Round30` is the architecture breakthrough round in this legacy batch. It
ultimately promoted `r30_b1_dironly` as the production baseline.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND30_EXTERNAL_COMPARE.md`
3. `selected/reports/ROUND30_ARCH_BREAKTHROUGH_DECISION_20260318_003739.md`
4. `selected/reports/ROUND30_ARCH_BREAKTHROUGH_SUMMARY_20260317_160002.md`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- External promotion proof: `selected/reports/ROUND30_EXTERNAL_COMPARE.md`
- Preserved GMF payloads: `gmf_results/`
- Preserved recon payloads: `reconstruct_progress_best_tradeoff_in_Cropped_Output_*/`

## Replay Support

`partial`

This directory preserves both the decision chain and in-tree GMF payloads, but
replay still depends on root tools and historical checkpoints outside this
directory.
