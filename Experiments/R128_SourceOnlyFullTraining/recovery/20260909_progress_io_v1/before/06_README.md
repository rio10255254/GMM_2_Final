# R128 — Source-only full training

Self-contained experiment on branch codex/r128-full-training. The user authorized completing preparation and then starting the full planned training. Physical instrument certification limits claims, and is not a prerequisite for this source-isolated research training.

Status2026-09-09: all preparation checks passed; full training started. The first run's256-update checkpoint, changed learned parameters, optimizer state and independently rebuilt consumed images were reconciled. The four-run study is still running, not complete/adopted. See [live progress](reports/TRAINING_PROGRESS.md), [preparation results](reports/R128_RESULTS.md) and results/launch_verification.json.

The model receives only the observed image. Four shared learned reconstruction updates retain a4xintensity representation with2xneural computation. There are no untrained geometry/confidence outputs and no assumed real PSF inside the network. Two matched training arms differ only in a post-forward true-simulator consistency objective; no simulation truth reaches the model input.

Completed data:512training parents,128development parents and128final generated-test parents. All768parents passed the unchanged formation checks;691nonflat geometries are unique. Independent parent geometry/seeds and controls were audited before training. Real/SEM images remain reused development evaluation only. Full planned training is8192updates per arm/seed, two arms and two independent starts, not an automatically promoted model.

Budget24GiB registered before allocation. Source contexts are newly rendered, not padded/resized old data. See the canonical methodology and preparation records for exact frozen settings, readiness and execution status.
