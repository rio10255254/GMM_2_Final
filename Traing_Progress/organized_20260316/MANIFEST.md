# organized_20260316 — Legacy Mainline Batch

| Field | Value |
|------|-------|
| Batch | `Traing_Progress/organized_20260316` |
| Scope | `Round23`-`Round31` legacy mainline + external compare chain + analysis + TTA side direction |
| Status | Historical mainline batch preserved in place |
| Canonical batch guide | `docs/index/LEGACY_ROUNDS_OPERATIONS.md` |
| Narrative history | `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` |
| Current truth | `PROJECT_CURRENT_STATE.md` |
| Replay policy | Use per-surface `README.md` / `MANIFEST.md`; do not assume whole-batch replay is self-contained |

## Start Here

1. `README.md` — batch context and round roles
2. `docs/index/LEGACY_ROUNDS_OPERATIONS.md` — operational guide for legacy surfaces
3. `round30/README.md` — final baseline-winning round in this batch
4. `round31/README.md` — formal B1 follow-up that closed the legacy mainline
5. `external_compare_r18_r22_r25_r26_r27_r28_r29/README.md` — final generic step_mag compare chain

## Guardrails

- This batch is a preserved historical working surface, not a new-style experiment directory.
- Do not rename subdirectories to match modern conventions.
- Add navigation and policy files around legacy artifacts instead of relocating reports, GMF outputs, or reconstructions.
- `round32/` may remain in-tree as preserved payload/runtime history, but its canonical governance surface is `Experiments/R32Sandbox/`.
