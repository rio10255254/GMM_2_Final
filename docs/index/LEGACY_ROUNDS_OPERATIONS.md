# Legacy Rounds Operations Guide

Last updated: 2026-04-08

## Purpose

This guide defines the operational surface for the legacy mainline batch under
`Traing_Progress/organized_20260316/`.

Use this guide when you need to:
- safely reopen `Round23` through `Round30`
- find the canonical decision and compare artifacts for a legacy round
- distinguish editable historical truth from curated mirrors in `docs/evidence/`
- understand whether a legacy surface is safe to replay, partial to replay, or historical-only

This file is not the long-form narrative history. For strategy and chronology, read:
- `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## Scope

Phase-1 legacy governance covers:
- `round23` through `round30`
- the `external_compare_*` directories used to validate the R25-R29 progression
- `analysis/`
- `tta_experiment/` and `tta_experiment/r26_tta_cross5/`

Not covered by this phase:
- `round31`
- `round32`

Those two rounds already flow into later governance surfaces (`PROJECT_CURRENT_STATE.md`,
`docs/evidence/`, `Experiments/R32Sandbox/`) and will be handled separately if needed.

## Support Levels

| Level | Meaning |
|------|---------|
| `safe` | Self-contained replay contract exists in the directory. |
| `partial` | Canonical artifacts and some inputs/outputs are preserved, but replay still depends on root tools or external checkpoints. |
| `historical-only` | Use for reading, auditing, and evidence lookup; do not assume turnkey replay from this directory alone. |

## Batch Start Here

1. `Traing_Progress/organized_20260316/README.md` — batch context and round roles
2. `Traing_Progress/organized_20260316/MANIFEST.md` — batch identity and scope boundaries
3. `Traing_Progress/organized_20260316/round30/README.md` — final baseline-winning round
4. `Traing_Progress/organized_20260316/external_compare_r18_r22_r25_r26_r27_r28_r29/README.md` — final generic step_mag compare chain

## Legacy Round Surfaces

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

## Compare Surfaces

| Surface | Role | Canonical output | Replay |
|--------|------|------------------|--------|
| `external_compare_round18_round22/` | Round18 vs Round22 tie-break compare | `reports/EXTERNAL_COMPARE_R18_R22_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25/` | promote R25 over older baselines | `reports/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26/` | promote R26 over R25 | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26_r27/` | test R27 against R26 | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26_r27_r28/` | falsify R28 downsweep | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26_r27_r28_r29/` | falsify R29 upper sweep | `reports/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.md` | `partial` |
| `external_compare_r18_r22_r25_r26r18_highcenter/` | preserved candidate payload surface | compare payload only | `historical-only` |
| `external_compare_r18_r22_r25_r26r22_hold/` | preserved candidate payload surface | compare payload only | `historical-only` |
| `external_compare_r18_r22_r25_r26r25_sw010/` | preserved candidate payload surface | compare payload only | `historical-only` |
| `external_compare_r18_r22_r25_r26r26_sm035/` | preserved candidate payload surface | compare payload only | `historical-only` |

## Side Surfaces

| Surface | Role | Canonical output | Replay |
|--------|------|------------------|--------|
| `analysis/` | internal/external screening analysis | `INTERNAL_EXTERNAL_CORRELATION.md` | `historical-only` |
| `tta_experiment/` | container for TTA side direction | see child surface | `historical-only` |
| `tta_experiment/r26_tta_cross5/` | R26 baseline vs TTA C2 compare | `reports/TTA_VS_BASELINE_CROSS5_COMPARISON.md` | `partial` |

## Editing Rules

- Do not rename or move legacy directories.
- Do not rewrite historical decision reports just to match new naming style.
- Add governance files (`README.md`, `MANIFEST.md`) around legacy surfaces instead of refactoring the original evidence layout.
- Treat `docs/evidence/` as curated mirror/index for these rounds unless `SOURCE_OF_TRUTH_POLICY.md` explicitly says otherwise.
- If a legacy surface only has raw recon / GMF payloads and no compare report, document it as `historical-only` instead of inventing a replay contract.
