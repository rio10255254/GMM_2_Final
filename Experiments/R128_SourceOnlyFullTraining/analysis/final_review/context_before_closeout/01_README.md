# R128 — Source-only full training

Self-contained experiment on branch codex/r128-full-training. The user authorized completing preparation and then starting the full planned training. Physical instrument certification limits claims, and is not a prerequisite for this source-isolated research training.

Final deployment requirement, reaffirmed2026-09-09: deliver one selected model with one usage entry point. The four training results are internal research comparisons; the assistant is responsible for evaluating and selecting, not handing four alternatives to the user. Selection must be supported by the complete fixed real microscopy/SEM evaluation and failure cases. The frozen training length and evaluation protocol remain in force; completion alone is not adoption.

Status2026-09-09 17:12Taipei: I/P seed1285001 completed their8192updates and scheduled evaluations. I seed1285002 lost both trainer/coordinator processes after5359updates, coinciding with a Codex update and NVIDIA event; unique cause remains unproven. The verified5248checkpoint resumes through recovery/20260909_external_stop/independent_entry.py, launched once by Windows services outside the application job. It calls the unchanged recovery coordinator and scientific trainer. See [current interruption audit](reports/R128_RUNTIME_CHECK_20260909.md), [live progress](reports/TRAINING_PROGRESS.md), and [earlier I/O repair](reports/R128_RECOVERY_20260909.md). All four runs are not yet complete.

The model receives only the observed image. Four shared learned reconstruction updates retain a4xintensity representation with2xneural computation. There are no untrained geometry/confidence outputs and no assumed real PSF inside the network. Two matched training arms differ only in a post-forward true-simulator consistency objective; no simulation truth reaches the model input.

Completed data:512training parents,128development parents and128final generated-test parents. All768parents passed the unchanged formation checks;691nonflat geometries are unique. Independent parent geometry/seeds and controls were audited before training. Real/SEM images remain reused development evaluation only. Full planned training is8192updates per arm/seed, two arms and two independent starts, not an automatically promoted model.

Budget24GiB registered before allocation. Source contexts are newly rendered, not padded/resized old data. See the canonical methodology and preparation records for exact frozen settings, readiness and execution status.
