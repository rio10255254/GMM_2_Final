# Repository Governance

## Purpose

This repository is the Git/GitHub management surface for `D:\GMM_2_Final`.

It is intentionally **not** a byte-for-byte mirror of the working directory on disk.
The goal is to track:

- source code
- formal project truth documents
- governance and workflow policy
- light, human-readable reports and manifests

It intentionally excludes large or reproducible payloads such as:

- training data
- model checkpoints
- reconstruction outputs
- raw GMF result dumps
- packaged runtimes and deployment bundles
- backup/archive directories

## Tracked Surface

The expected tracked surface is:

- root formal docs and policy files
- `Model/`
- `Tools/` excluding packaged bundles and local watcher state
- `PSF_Fitting/`
- `Experiments/R32Sandbox/` code, docs, runtime status, manifests, and light reports

The expected untracked surface is:

- `Traing_Progress/`
- `Training_Data/`
- `_deployment_package/`
- backup/archive directories
- bulk subdirectories such as `weights/`, `artifacts/`, `logs/`, `reconstructions/`, `gmf_results/`

## Branch Taxonomy

- `main`
  - the curated shared mainline
- `snapshot/initial-import-2026-03-23`
  - the first curated Git import on `2026-03-23`
  - this is a repository snapshot of the tracked surface, not a byte-for-byte disk mirror
- `baseline/r30-b1-dironly`
  - the current production baseline
- `reconstructed/r26-sm035`
  - evidence-backed predecessor baseline
- `reconstructed/round30-architecture-breakthrough`
  - the milestone where `Round30 / r30_b1_dironly` became the adopted baseline
- `research/round31-b1-hparam`
  - the measured hyperparameter study that regressed externally
- `sandbox/r32`
  - the isolated `R32Sandbox` execution surface
- `research/r32-post-falsification`
  - the semantic placeholder for future post-falsification work

## Reconstruction Honesty Rule

This repository did not start with preserved git history.

Therefore:

- reconstructed branches must say that they are reconstructed
- semantic branches must say that they are semantic
- no branch should claim to be the original historical git state without direct evidence

## Update Rules

When the project truth changes:

1. update `PROJECT_SESSION_CONTINUITY.md` if cross-interface handoff changed
2. update `PROJECT_CURRENT_STATE.md` if current truth or next decision boundary changed
3. update `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` if stable rules changed
4. update this file if the tracked surface or branch taxonomy changed
