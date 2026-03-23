# Evidence Layer

This directory holds curated tracked copies of small, high-value experiment
evidence that is worth keeping in GitHub.

It exists to preserve the formal proof surface for the current baseline and
major falsified branches without pulling bulk experiment outputs into Git
history.

## What Belongs Here

- formal decision memos
- external compare summaries
- small machine-readable compare JSON files
- small canonical runtime truth snapshots

## What Does Not Belong Here

- weights
- reconstructions
- raw GMF dumps
- bulk logs
- images or other large reproducible payloads

Those stay in their original experiment/output locations and remain outside the
tracked evidence layer.

## Why These Are Curated Copies

Files in this directory are copied from their original runtime or report
locations so the repository can keep a stable, reviewable evidence surface.

The source files remain in place. This directory is not the original execution
root and should not be treated as a live runtime directory.

## Layout

- `baseline/`
  - evidence that supports the current promoted baseline
- `falsified/`
  - evidence that supports formally rejected or externally failed lines
- `runtime/`
  - small canonical runtime truth snapshots that are worth tracking

## Current Core Set

- `baseline/ROUND30_ARCH_BREAKTHROUGH_DECISION_20260318_003739.md`
  - supports `baseline/r30-b1-dironly` internal decision
- `baseline/ROUND30_EXTERNAL_COMPARE.md`
  - supports the external promotion of the current baseline
- `falsified/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
  - explains the Round31 B1 follow-up line
- `falsified/ROUND31_EXTERNAL_COMPARE.md`
  - supports `research/round31-b1-hparam` external regression
- `falsified/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
  - explains the Round32 internal winner selection
- `falsified/ROUND32_EXTERNAL_COMPARE.md`
  - supports `sandbox/r32` external FAIL in human-readable form
- `falsified/ROUND32_EXTERNAL_COMPARE.json`
  - machine-readable companion to the Round32 external FAIL verdict
- `runtime/R32_STATUS.md`
  - current canonical sandbox runtime truth in human-readable form
- `runtime/R32_STATUS.json`
  - machine-readable companion to the canonical sandbox runtime truth
