# organized_20260313 — Legacy Batch

| Field | Value |
|------|-------|
| Batch | `Traing_Progress/organized_20260313` |
| Scope | `round16`-`round19` mainline rounds + `root_status_legacy` status bridge |
| Status | Historical legacy batch preserved in place |
| Canonical batch guide | `docs/index/LEGACY_ROUNDS_OPERATIONS.md` |
| Narrative history | `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` |
| Current truth linkage | `PROJECT_STATE.md` for promoted descendants, `root_status_legacy/` for preserved batch status |
| Replay policy | Use per-surface `README.md` / `MANIFEST.md`; do not assume whole-batch replay is self-contained |

## Start Here

1. `README.md`
2. `docs/index/LEGACY_ROUNDS_OPERATIONS.md`
3. `round18/README.md`
4. `round19/README.md`
5. `root_status_legacy/README.md`

## Guardrails

- This batch is a preserved historical working surface, not a new-style experiment directory.
- Do not rename `round16`-`round19` or flatten their `selected/archive/pending` layout.
- Add governance files around the existing evidence chain instead of moving status snapshots, audit outputs, or external validation payloads.
