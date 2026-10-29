# Project cleanup candidates - 2026-08-11

## Decision

No historical research payload was removed during the R92 setup. D still had 171.42 GiB free at the final snapshot, so there was no need for an emergency destructive cleanup. R91 had completed all 60 epochs; Git maintenance was still writing, so free space may continue to move until Git finishes. Every candidate below remains blocked until its remaining evidence and approval checks pass.

The only removals already completed were reproducible R92 setup intermediates inside the new experiment: 99.31 MiB of failed early smoke data and 71.55 MiB of a superseded smoke copy whose metadata name was corrected and then regenerated. The final R92 smoke data, audit, checkpoint and reports were retained and reverified. No prior-round research payload was removed.

## Protected now

- `Experiments/R91_DetailDecoupledScratch`: training complete, all data and outputs remain protected until full analysis and checkpoint selection closeout.
- `Experiments/R92_PhysicalTransitionBalancedScratch`: frozen setup and smoke evidence protected; formal data does not exist yet.
- Raw acquisitions, SEM sources, thesis evidence, formal datasets, adopted checkpoints and current model packages are not cleanup candidates.
- `.git`: Git fetch and repack processes were active at the snapshot, so no Git object or temporary pack may be touched.

## First reclaim candidates

### R89 failed generated payloads - 15.5257 GiB

Exact target: `Experiments/R89_MeasurementNativeScratch/runs/failed_data_generation`

- `20260811_pixelwise_clipping_leakage`: 13.4953 GiB, 8,241 files. Rejected because the old source-generation rule could copy target-shaped detail into the input.
- `20260811_progress_lock_failure`: 2.0304 GiB, 1,222 files. Contains only 100 of 1,280 planned formal scenes and 40 of 384 planned holdout scenes; neither partial set has a sealed final manifest.

A compact incident record now preserves the failure reasons, original sizes, generator identities, partial counts, audit hashes, and exact linkage to the complete successful R89 data. R91 has exited, so the two payloads now require only exact-path remeasurement and explicit removal approval before deletion.

### Old pytest caches - 2.2362 GiB

- `Thesis_MOSR_Evidence/.tmp/pytest`: 0.3561 GiB.
- `Thesis_MOSR_Evidence/.tmp/pytest-of-Rio`: 1.8801 GiB.

These are rebuildable. Remove only after confirming that no pytest process is using them.

### Interrupted Git pack - 19.3646 GiB

Exact candidate: `.git/objects/pack/tmp_pack_8aJBWz`

This cannot be treated as an ordinary temporary file. Before any removal, Git must be idle, repository integrity must pass, and Git itself must confirm that the file is unreachable garbage. Git maintenance was active at the snapshot, so the candidate is locked.

## Archive-first candidate

### R63 completed causal ablation - 51.4805 GiB

R63 is complete, but its training histories and reconstruction outputs are still valid experimental evidence. The safe action is:

1. Copy the entire R63 experiment to `H:\GMM_2_Final_Archive\experiments\R63_CausalBoundaryMotionAblation\20260811_full_history`.
2. Produce a complete SHA-256 manifest and verify the H copy file by file.
3. Keep on D the readable reports, protocol and revision history, scripts, tests, settings, aggregate result tables, final figures, training manifest, verification receipts and a restore pointer.
4. Only after explicit approval, remove the verified heavy training-run and reconstruction payloads from D.

This could reclaim most of 51.48 GiB while preserving a complete restorable history.

## Approval boundary

No command should delete or move the candidates above using a wildcard. A cleanup execution must name the exact resolved paths, record current sizes and hashes, confirm active processes are absent, and report what was removed and how it can be restored.
