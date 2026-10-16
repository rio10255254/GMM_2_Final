# R126 identity

- Profile: self-contained, isolated new diagnostic/training launchers with explicit run IDs.
- Previous model and data: R125, read only; its model is imported without editing.
- Stage 1: four 128-update fixed-example controls, same initial learned tensor bank; observation on/off x original image-related objective/image-only.
- Stage 2: scope and exact protocol frozen separately after Stage 1 diagnosis and before any Stage 2 training or real outputs.
- Capacity: registered 4 GiB before allocation; no archive/deletion.
- Completion: same-run ledgers, final checkpoints, semantic checks, real evaluations and canonical scientific decision. No baseline promotion.

Completed scope:6fixed-example runs(768updates),4photometry runs(512updates),8real evaluations,144real float outputs,1152SEM rows,48motion rows,216simulation diagnostic view rows. P/Q initial/final models remain in `runs/photometry_initial` and `runs/photo_{P|Q}_s{1265001|1265002}`. No selected winner or checkpoint pruning. The initial trace mismatch and same-runtime repair are both retained. Canonical scientific decision is `reports/R126_RESULTS.md`; final verification is separate from model usefulness.
