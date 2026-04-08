# organized_20260314 — Legacy Batch

| Field | Value |
|------|-------|
| Batch | `Traing_Progress/organized_20260314` |
| Scope | `round20` process probe + `diagnostics` branch-selection surface + `branch_e` estimator-side branch |
| Status | Historical transition batch preserved in place |
| Canonical batch guide | `docs/index/LEGACY_ROUNDS_OPERATIONS.md` |
| Narrative history | `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` |
| Current truth linkage | Branch-selection outcome feeds the later `round21` / `round22` lineage |
| Replay policy | Use per-surface `README.md` / `MANIFEST.md`; do not assume whole-batch replay is self-contained |

## Start Here

1. `README.md`
2. `docs/index/LEGACY_ROUNDS_OPERATIONS.md`
3. `round20/README.md`
4. `diagnostics/README.md`
5. `branch_e/README.md`

## Guardrails

- This batch is a preserved historical decision surface, not a new-style experiment directory.
- Keep `round20`, `diagnostics`, and `branch_e` in place; do not merge them into a synthetic single round.
- Add governance files around existing probe and archive content instead of relocating reports or logs.
