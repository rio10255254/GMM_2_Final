# R93 Manifest

## Identity

- Round: `R93`
- Name: `RecoverableDetailSeparatedScratch`
- Role: independent research candidate; no baseline change
- Parent evidence: R91 root-cause analysis only
- Checkpoint inheritance: prohibited

## Reproducibility contract

- Master seed: `930041` (actual frozen formal manifest; the old template used 920041)
- Formal scale: `1,250 scenes x 4 observations = 5,000 observations`
- Label construction: `8x supersampling -> one area reduction`
- Formal runs: one independent run; actual execution planned 64 epochs and stopped after complete epoch 60
- Training selection: procedural validation only
- Primary validation and deployment reference: float32, tile batch one; bfloat16 is diagnostic only
- Exposure reporting: four predeclared path regions plus the continuous worst-path contour ratio
- Raw protection: continuous procedural boundary non-inferiority, never a binary gate
- Recoverability correction: only a traceable global source photometric projection, with original-array backup and complete re-hash; no target-pixel mixing
- Unprojectable synthetic observation: deterministic full rerender inside the same degradation family only, with exact backup and complete re-hash
- Real microscope images: fixed visual previews only, never loss, selection, or training input

## Main entry points

- Dataset builder: `scripts/generate_dataset.py`
- Training launcher: `scripts/launch_r93.py`
- Training program: `training/train_r93.py`
- Reconstruction: `inference/reconstruct.py`
- Foreground monitor: `scripts/monitor_training.ps1`
- Design validation: `scripts/validate_design.py`
- Execution validation: `scripts/validate_execution.py`

## Storage contract

Bulk data, runs, results, and weights remain experiment-local and outside Git. No R91 payload is copied into R93. Old experiment payloads may be archived only through a hash-verified, reversible operation.

### 2026-10-22 storage update

Only the duplicate D `data/r93_formal/arrays` and `data/r93_locked_holdout/arrays` have been removed after all 18,072 files matched the fixed H archive and the original generator's array-content hashes. Models, complete result tables, reports, data records, the holdout seal, previews, smoke data and original camera inputs remain. Restore the fixed arrays before using the original full-training or data-validation paths for R93 or its R94–R98 dependents; follow [the archive and restore guide](data/ARCHIVE_POINTER_20261022.md). This storage operation does not evaluate the sealed holdout or change any scientific verdict. The earlier experiment-local storage statement above is the historical contract.

## 2026-10-20 provenance correction

The actual formal dataset contains 15,004 files, 29,704,604,438 bytes and content identity `6494719ad21665723ba32cdcb3871a40691753ca03791f181416349f02fd31a5`. Its 1,250 scenes split into 1,000 train, 125 validation and 125 internal-test scenes. The separate sealed holdout is not part of the new replay checks.

The actual stopped-run record selects epoch 48 as the balanced internal candidate; the last complete model is epoch 60. The old manifest is preserved in [history](../../docs/history/R93_MANIFEST_BEFORE_PROVENANCE_AUDIT_20261020.md). No generator, training configuration, checkpoint, original image, numerical result or formal estimator policy value was changed by this correction.

See [the canonical provenance audit](reports/R93_AUDIT.md) and [the GitHub recovery guide](../../docs/reproducibility/r93_shared/README.md).
