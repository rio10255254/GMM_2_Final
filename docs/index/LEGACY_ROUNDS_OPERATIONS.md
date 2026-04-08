# Legacy Rounds Operations Guide

Last updated: 2026-04-08

## Purpose

This guide defines the operational surface for the preserved legacy batches
under:

- `Traing_Progress/organized_20260313/`
- `Traing_Progress/organized_20260314/`
- `Traing_Progress/organized_20260315/`
- `Traing_Progress/organized_20260316/`

Use this guide when you need to:
- safely reopen `Round16` through `Round31`
- find the canonical decision and compare artifacts for a legacy round
- follow the handoff path from `round18` and `round22` into the later external compare chain
- distinguish editable historical truth from curated mirrors in `docs/evidence/`
- understand whether a legacy surface is safe to replay, partial to replay, or historical-only

This file is not the long-form narrative history. For strategy and chronology, read:
- `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## Scope

Phase-1 / phase-2 legacy governance covers:
- `organized_20260313` (`round16`-`round19`, `root_status_legacy`)
- `organized_20260314` (`round20`, `diagnostics`, `branch_e`)
- `organized_20260315` (`round21`, `round22`, `pairwise_delta_probe`, `branch_e_followup`, `estimator_formula_probe`)
- `organized_20260316` (`round23`-`round31`, compare chain, `analysis`, `tta_experiment`)

Still not covered by this guide:
- `round32/` payloads preserved under `organized_20260316/`
- `Experiments/R32Sandbox/`

`Round31` remains a governed legacy round in `organized_20260316/`.
`Round32` already flows into later governance surfaces (`PROJECT_CURRENT_STATE.md`,
`docs/evidence/`, `Experiments/R32Sandbox/`) and is handled there instead of
by this guide.

## Support Levels

| Level | Meaning |
|------|---------|
| `safe` | Self-contained replay contract exists in the directory. |
| `partial` | Canonical artifacts and some inputs/outputs are preserved, but replay still depends on root tools or external checkpoints. |
| `historical-only` | Use for reading, auditing, and evidence lookup; do not assume turnkey replay from this directory alone. |

## Batch Start Here

1. `Traing_Progress/organized_20260313/MANIFEST.md` — `round16`-`round19` and status-bridge batch
2. `Traing_Progress/organized_20260314/MANIFEST.md` — transition batch from `round20` into `branch_e`
3. `Traing_Progress/organized_20260315/MANIFEST.md` — estimator-side batch for `round21` / `round22`
4. `Traing_Progress/organized_20260316/MANIFEST.md` — external-compare and mainline breakthrough batch

## Cross-Batch Lineage

1. `round18` becomes the adopted internal baseline of `organized_20260313`
2. `round22` becomes the next legacy baseline of `organized_20260315`
3. `external_compare_round18_round22/` resolves that tie-break inside `organized_20260316`
4. `round25` through `round30` build the external compare chain on top of those earlier preserved baselines

## organized_20260313

| Surface | Role | Verdict | Replay |
|--------|------|---------|--------|
| `root_status_legacy/` | preserved root longrun snapshots | status bridge only | `historical-only` |
| `round16/` | `EDGEFIT` estimator-shift round | internal winner, later superseded | `partial` |
| `round17/` | `STEPFIX` recovery round | internal winner, later superseded | `partial` |
| `round18/` | `CENTERPUSH` adopted internal baseline | adopted, later compared against `round22` | `partial` |
| `round19/` | `ABSANCHOR` falsification | completed, not adopted | `partial` |

## organized_20260314

| Surface | Role | Verdict | Replay |
|--------|------|---------|--------|
| `round20/` | baseline-lock process probe | hypothesis not supported | `partial` |
| `diagnostics/` | branch-selection diagnostics | chose `Branch E` | `historical-only` |
| `branch_e/` | estimator-side probe branch | advanced into later follow-up, not final baseline | `partial` |

## organized_20260315

| Surface | Role | Verdict | Replay |
|--------|------|---------|--------|
| `round21/` | formal hybrid-estimator follow-up | failed to unblock mainline | `partial` |
| `round22/` | formal `pairmix_algblend` validation | adopted legacy baseline, later externally compared | `partial` |
| `pairwise_delta_probe/` | side probe that generated `pairmix_algblend` | passed internal probe and fed `round22` | `partial` |
| `branch_e_followup/` | calibrated reevaluation of `Branch E` | still blocked before promotion | `partial` |
| `estimator_formula_probe/` | early estimator-formula exploration | preserved for lineage only | `historical-only` |

## organized_20260316 Mainline Rounds

| Surface | Role | Verdict | Replay |
|--------|------|---------|--------|
| `round23/` | pairmix abs-center diagnostic | diagnostic only, no promotion | `historical-only` |
| `round24/` | single-frame abs-center diagnostic | diagnostic only, no promotion | `historical-only` |
| `round25/` | first scratch abs-center external breakthrough | promoted over earlier baselines, later superseded | `partial` |
| `round26/` | step recovery and baseline promotion | promoted to `r26_sm035`, later superseded by R30 | `partial` |
| `round27/` | recovery frontier after R26 | internal frontier, external no-upgrade | `partial` |
| `round28/` | `step_mag < 0.35` downsweep falsification | falsified | `partial` |
| `round29/` | `step_mag > 0.35` upper sweep falsification | falsified | `partial` |
| `round30/` | architecture breakthrough | promoted to `r30_b1_dironly` baseline | `partial` |
| `round31/` | B1 hyperparameter follow-up | completed external compare, no promotion | `partial` |

## organized_20260316 Compare Surfaces

| Surface | Role | Canonical output | Replay |
|--------|------|------------------|--------|
| `external_compare_round18_round22/` | `round18` vs `round22` tie-break compare | `reports/EXTERNAL_COMPARE_R18_R22_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25/` | promote `round25` over older baselines | `reports/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26/` | promote `round26` over `round25` | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26_r27/` | test `round27` against `round26` | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26_r27_r28/` | falsify `round28` downsweep | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26_r27_r28_r29/` | falsify `round29` upper sweep | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26r18_highcenter/` | preserved candidate payload surface | compare payload only | `historical-only` |
| `external_compare_r18_r22_r25_r26r22_hold/` | preserved candidate payload surface | compare payload only | `historical-only` |
| `external_compare_r18_r22_r25_r26r25_sw010/` | preserved candidate payload surface | compare payload only | `historical-only` |
| `external_compare_r18_r22_r25_r26r26_sm035/` | preserved candidate payload surface | compare payload only | `historical-only` |

## organized_20260316 Side Surfaces

| Surface | Role | Canonical output | Replay |
|--------|------|------------------|--------|
| `analysis/` | internal/external screening analysis | `INTERNAL_EXTERNAL_CORRELATION.md` | `historical-only` |
| `tta_experiment/` | container for TTA side direction | see child surface | `historical-only` |
| `tta_experiment/r26_tta_cross5/` | `R26` baseline vs TTA C2 compare | `reports/TTA_VS_BASELINE_CROSS5_COMPARISON.md` | `partial` |

## Editing Rules

- Do not rename or move legacy directories.
- Do not rewrite historical decision reports just to match new naming style.
- Add governance files (`README.md`, `MANIFEST.md`) around legacy surfaces instead of refactoring the original evidence layout.
- Treat `docs/evidence/` as curated mirror/index for these rounds unless `SOURCE_OF_TRUTH_POLICY.md` explicitly says otherwise.
- If a legacy surface only has raw recon / GMF payloads and no compare report, document it as `historical-only` instead of inventing a replay contract.
