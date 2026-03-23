# Repository Governance

## Purpose

This repository is the Git/GitHub management surface for `D:\GMM_2_Final`.

It is intentionally **not** a byte-for-byte mirror of the working directory on disk.
The goal is to track:

- source code
- formal project truth documents
- governance and workflow policy
- light, human-readable reports and manifests
- small canonical sample fixtures when they are intentionally retained for reproducible references

It intentionally excludes large or reproducible payloads such as:

- training data
- model checkpoints
- reconstruction outputs
- raw GMF result dumps
- packaged runtimes and deployment bundles
- backup/archive directories

Small, deliberate, auditable sample fixtures are allowed when they provide a stable reference input for code, docs, or review. For example, `Model/Test_Image/VisionTop_20251029182653732.bmp` is retained as a canonical sample fixture rather than as bulk experiment output.

## Tracked Surface

The expected tracked surface is:

- root formal docs and policy files
- `docs/` navigation, history, analysis, and curated legacy references
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
- root runtime outputs such as regenerated `000_LONGRUN_*` status files

## Documentation Layout

This repository keeps the root intentionally small.

- root
  - entry-point docs, governance docs, machine-readable policy, and core code directories
- `docs/history/`
  - long-form historical narrative
- `docs/index/`
  - documentation responsibility map and navigation index
- `docs/analysis/`
  - research path maps and visual summaries
- `docs/runtime/legacy/`
  - curated, tracked copies of legacy root runtime status files

If an older launcher recreates `000_LONGRUN_*` files at the repository root, treat them as local execution outputs only. The Git-tracked copies live under `docs/runtime/legacy/root_status/`.

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

- reconstructed branches must say that they are reconstructed governance/reference branches built on top of the curated import
- semantic branches must say that they are semantic
- no branch should claim to be the original historical git state or a recovered historical tree without direct evidence

## Sync Cadence

Push to GitHub when any of the following changes:

- a major branch is created or materially reframed
- a strategy attempt becomes formalized enough to deserve tracked docs
- a baseline, verdict, or active direction changes
- an important experiment analysis or decision memo is added
- the repository information architecture or governance rules change

Do not push day-to-day runtime log spam, ephemeral watcher output, or local execution noise just to keep the cloud “live.”

## Update Rules

When the project truth changes:

1. update `PROJECT_SESSION_CONTINUITY.md` if cross-interface handoff changed
2. update `PROJECT_CURRENT_STATE.md` if current truth or next decision boundary changed
3. update `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` if stable rules changed
4. update this file if the tracked surface or branch taxonomy changed
