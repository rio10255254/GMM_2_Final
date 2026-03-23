# Contributing

## Repository Scope

This repository is a curated research-code repo.

Tracked content:

- source code in `Model/`, `Tools/`, and selected `Experiments/R32Sandbox/` code/docs
- project truth docs and governance docs at the repo root
- light reports, manifests, and policies that explain decisions
- PSF fitting source and supporting documentation

Intentionally untracked content:

- `Traing_Progress/`
- `Training_Data/`
- `_deployment_package/`
- bulk artifacts such as `weights/`, `artifacts/`, `logs/`, `reconstructions/`, `gmf_results/`
- portable runtimes, backup folders, and editor-local state

If a result is reproducible from tracked code or can live in external storage, keep it out of Git history.

## Canonical Reading Order

Start here when taking over the project:

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. `PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## Branch Strategy

- `main`: curated shared mainline for tracked code, docs, and governance
- `baseline/*`: production baselines
- `reconstructed/*`: evidence-backed historical snapshots, clearly labeled as reconstructed
- `research/*`: semantic research branches that preserve intent without pretending to be original git history
- `sandbox/*`: isolated experimental surfaces such as `R32`

Do not claim that a reconstructed branch is the original historical git state unless that state is verifiably preserved.

## Pull Requests

Before opening a PR:

1. Verify that no bulk artifacts or data are staged.
2. Update the relevant formal docs if the baseline, verdict, or active experiment changed.
3. Explain the change in terms of external GMF truth, baseline policy, and branch taxonomy where relevant.

## Issues

- Use the research round proposal template for new branches or rounds.
- Use the bug report template for defects in tracked source, docs, or governance.
- Link to external reports instead of uploading large files into GitHub.
