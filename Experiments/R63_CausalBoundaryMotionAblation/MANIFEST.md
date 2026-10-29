# R63 Manifest

## Identity

- Round: `R63`
- Name: `CausalBoundaryMotionAblation`
- Role: thesis-focused research experiment; not a formal baseline change
- Date opened: `2026-07-16`
- Workspace branch at opening: `sandbox/r45` (dirty shared worktree; preserved without switching)

## Fixed source assets

- Model package: `Deliverables/Standalone_Models/V42_SoftLabelSNR_FullStandalone_20260709`
- Starting checkpoint: package-local `weights/base_v41_standalone_best_tradeoff.pth.tar`
- Fixed split: package-local `training_data/splits/grouped_seed1337_val120`
- PSF: package-local `psf/PSF_fitted_2D_FOVstack.mat`

## Reproducibility contract

- Seeds: `1261200`, `1261217`
- CUDA execution: match the standalone full-training run (CuDNN benchmark and TF32 enabled, AMP disabled)
- Repeatability: two fixed seeds plus an optional strict deterministic forensic mode
- Main / validation / sequence batch sizes: `8 / 2 / 2`, matching the standalone full-training launcher
- Data-loader workers: `4`, with the package-local fixed split loaded in every run
- Same data split and batch budget for every matched comparison
- PSF and all optical settings: fixed, never ablated
- Runtime config snapshot: required before each run
- Checkpoints: saved every four epochs and at selection points
- Matched retraining budget: `40 epochs x 32 main batches/epoch`, globally extended to 60 epochs when the predeclared convergence gate triggers
- Training candidates: four factorial endpoints, seven loss-component removals, three output-module removals, and one matched upsampling pair (16 conditions total)

## Handoff

- Launcher: `scripts/launch_r63.py`
- Protocol: `PROTOCOL.md`
- Pre-metric revision log: `PROTOCOL_REVISION_LOG.md`
- Result report: `reports/R63_RESULTS.md`
- Portable report: `reports/R63_RESULTS.html`
- Canonical portable-report payload: `reports/artifact.json`
- Portable report QA receipt: `results/portable_report_qa.json`
- Training records: `results/training_runs/`
- Config snapshots: `results/config_snapshots/`
- Evaluation records: `results/evaluation/`
- Machine-readable key findings: `results/evaluation/aggregate/R63_key_findings.csv`
- Figure index and intended use: `CHART_MAP.md`

## Completion

- Valid matched runs: `32 / 32`
- Candidate reconstructions: `18,272 / 18,272`
- Figure exports: `24 PNG + 24 PDF`
- Automated tests: `15 passed`
- Thesis files modified by this round: `0`
