# R134 Manifest

P1 precision revision: `precision_revision/` contains an isolated protocol, exact-value IO, matched SEM/motion requalification, package blueprint, conditional continuation and final evaluation. Its `results/status.json` is the active execution state. Original `results/long_admission.json` and frozen sources remain unchanged. Each qualified long-training generation receives its own package; P1 planned package is R134_DirectState_Precision_Standalone_20260915, created only after actual qualification.

Profile: local model/trainer, immutable shared data. A/C whole-interface factor; B/D pending actual calibration. Preserve all trials/failures; no auto-accept of old hashes. Long-worthy generations packaged individually, no automatic promotion.

- `config/study.json`: prospective matched short-training design, unchanged after results.
- `config/full_motion_admission.json`: prospective full201 screening rules.
- `runs/`: all four fresh512update runs, optimizer/checkpoint/input records.
- `results/real/`, `results/motion/`: completed shared SEM and12pair outputs, including all comparisons.
- `results/full_motion/`: selected-by-dev C full201 qualification, initially in progress.
- `scripts/continue_qualified134.py`: active fail-closed qualification/package/training continuation.
- `config/packaging_source_binding.json`: current-source freeze for FUTURE packaging, not retroactive evidence of the initial training source.
- `package_templates/`, `scripts/build_long_package134.py`: independently verified-at-build package preparation; these templates alone are not a delivered package.
- `results/continuation/`: live stage, actual package checks, failures and manual-control logs.
- `scripts/compare_long134.py`: endpoint full201 comparison after eligible long training; no default model promotion.
- `reports/R134_RESULTS.md`: canonical actual-result report, updated by execution phase; previous versions retained in results/index_history.
- `STATUS_R134.cmd`: read-only human status; it does not start duplicate training.

Completion criteria: short comparisons and independent readouts, full201 qualification, individual package actual portability/resume/readout checks, eligible long run with all scheduled evaluations, final full201 readout. B/D remain separately incomplete until genuine independent calibration is supplied. No completion flag can substitute for these measured outputs.

Cross-axis follow-up: cross_axis_diagnosis (468centerrows), cross_axis_precision_v2 (234centerrows), cross_axis_analysis (702independentrefits, figures, cohort context); retain initial precision-test failure. Canonical R134_CROSS_AXIS_DIAGNOSIS.md. Original admission and frozen packaging sources unchanged; no long training triggered.
