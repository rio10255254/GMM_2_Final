# organized_20260315 — Legacy Batch

| Field | Value |
|------|-------|
| Batch | `Traing_Progress/organized_20260315` |
| Scope | `round21`, `round22`, `pairwise_delta_probe`, `branch_e_followup`, `estimator_formula_probe` |
| Status | Historical estimator-side batch preserved in place |
| Canonical batch guide | `docs/operations/LEGACY_ROUNDS_OPERATIONS.md` |
| Narrative history | `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` |
| Current truth linkage | This batch feeds the later `round22` legacy baseline and the `external_compare_round18_round22` tie-break |
| Replay policy | Use per-surface `README.md` / `MANIFEST.md`; do not assume whole-batch replay is self-contained |

## Start Here

1. `README.md`
2. `docs/operations/LEGACY_ROUNDS_OPERATIONS.md`
3. `round22/README.md`
4. `pairwise_delta_probe/README.md`
5. `branch_e_followup/README.md`

## Guardrails

- This batch mixes formal rounds and side probes; keep those surfaces separate.
- Do not rename directories to force them into modern experiment conventions.
- Add governance files around existing evidence instead of moving postmortems, probe summaries, or archive content.
