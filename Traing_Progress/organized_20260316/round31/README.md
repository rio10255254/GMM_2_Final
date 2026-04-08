# round31 — B1 Hyperparameter Follow-up

## Purpose

`Round31` is the formal B1 hyperparameter follow-up on top of
`r30_b1_dironly`. It tests whether measured B1 tuning can beat the newly
promoted `Round30` baseline without changing the core architecture.

## Start Here

1. `MANIFEST.md`
2. `selected/reports/ROUND31_EXTERNAL_COMPARE.md`
3. `selected/reports/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
4. `selected/reports/ROUND31_B1_HYPERPARAM_SUMMARY_20260318_113707.md`
5. `selected/current_round31_b1_hyperparam_seed.json`

## Canonical Surface

- Human-readable decision truth: `selected/reports/*.md`
- Machine-readable decision truth: `selected/reports/*.json`
- External compare proof: `selected/reports/ROUND31_EXTERNAL_COMPARE.md/json`
- Selected seed: `selected/current_round31_b1_hyperparam_seed.json`
- Preserved GMF payloads: `gmf_results/`
- Preserved recon payloads: `reconstruct_progress_best_tradeoff_in_Cropped_Output_*/`

## Replay Support

`partial`

This directory preserves the internal decision chain and the completed external
compare artifacts, but replay still depends on root tools and historical
checkpoints outside this directory alone.
