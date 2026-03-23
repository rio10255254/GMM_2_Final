# Evidence Layer

This directory holds curated tracked copies of small, high-value experiment
evidence that is worth keeping in GitHub.

It exists to preserve the formal proof surface for:

- the current promoted baseline
- the historical baseline path that led to the current baseline
- major falsified branches
- side-direction falsifications
- analysis and screening evidence
- small canonical runtime truth snapshots

without pulling bulk experiment outputs into Git history.

## What Belongs Here

- formal decision memos
- external compare summaries
- small machine-readable compare JSON files
- small canonical runtime truth snapshots
- compact analysis / screening reports

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

## First Stop

If you want to understand the evidence chain quickly, read:

- `EVIDENCE_MAP.md`

That file explains which evidence supports the current baseline, the historical
baseline path, major falsified lines, side-direction rejections, analysis
conclusions, and runtime truth.

## Layout

- `baseline/`
  - evidence that supports the current promoted baseline
- `historical_baselines/`
  - evidence that explains the pre-R30 baseline path and the generic `step_mag`
    line that culminated in `R26 sm035`
- `falsified/`
  - evidence that supports formally rejected or externally failed lines
- `side_directions/`
  - evidence that formally rejects important side-direction attempts such as TTA
- `analysis/`
  - evidence that supports screening logic or cross-run analytical conclusions
- `runtime/`
  - small canonical runtime truth snapshots that are worth tracking
- `EVIDENCE_MAP.md`
  - one-file map of which evidence supports which verdict or branch

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

## Historical Baseline Path

- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.md`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.json`
  - documents the step from the earlier `R18/R22` references to `Round25`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.json`
  - shows the next formal compare step that established the `R26` line
- `historical_baselines/ROUND29_STEP_MAG_UPPER_DECISION_20260317_124715.md`
- `historical_baselines/ROUND29_STEP_MAG_UPPER_DECISION_20260317_124715.json`
  - explains the formal upper-sweep decision logic around `Round29`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.md`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.json`
  - preserves the strongest compact proof that `R26 sm035` remained the
    externally verified optimum of the generic `step_mag` line

## Additional Falsified / Analysis Evidence

- `falsified/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.json`
- `falsified/ROUND31_EXTERNAL_COMPARE.json`
- `falsified/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.json`
  - machine-readable companions for the core Round31 / Round32 falsified lines
- `analysis/INTERNAL_EXTERNAL_CORRELATION.md`
- `analysis/INTERNAL_EXTERNAL_CORRELATION.json`
  - supports the `center_err` Tier2 screening conclusion
- `side_directions/TTA_VS_BASELINE_CROSS5_COMPARISON.md`
- `side_directions/TTA_VS_BASELINE_CROSS5_COMPARISON.json`
  - preserves the formal rejection of the `TTA C2` side direction

## Curation Rule

This directory is intentionally selective.

- It should grow when a document materially supports the current baseline,
  a key historical baseline transition, a major falsified line, or a durable
  analytical conclusion.
- It should not grow just because a report exists in an experiment directory.
- Per-candidate audits, batch manifests, auto-tune noise, images, and bulk
  raw outputs stay outside Git unless there is a strong reviewable reason to
  curate them here.
