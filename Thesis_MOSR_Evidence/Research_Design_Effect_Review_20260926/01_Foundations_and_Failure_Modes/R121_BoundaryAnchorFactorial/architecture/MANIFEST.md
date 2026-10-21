# R121 evidence and execution scope

Profile: self-contained. Canonical local model/training/inference sources are
under this directory. No teacher or inherited checkpoint is used for new runs.

Shared immutable inputs: R118_PhysicalCoordinateRepairScratch/data/package and
R120_PhysicalSequenceRepair/data/sequences. Their identity is recorded in
reports/protected_inputs.json. No writes may pass into those references.

The eight 12-epoch runs are bounded research probes, not a formal 42-epoch launch.
Identity is bound to run_id in state, checkpoints, inference and measurements;
this native runner does not use a legacy trainer.MODEL_NAME_BASE variable.

Keep code, protocols, initializations, per-epoch logs, E4/E8/E12 checkpoints,
failures, shared validation and reference audit. The storage registry budgets
8 GiB before training. No deletion or archival occurs in this task.

Reports and scientific judgments are independent of completion flags. A finished
process or matching hash certifies neither a faithful experiment nor an improved
model. Never refresh old R118/R119 protection snapshots or receipts.

## Evaluated outcome

Eight valid 12-epoch probes completed and were measured. B/C/D are not adopted:
both seeds fail shape and texture conditions under both SEM references. The
controlled-motion guard alone passes. Conditional real LSC was not triggered;
there is no new real-LSC or long-training result.

The valid matrix is results/matrix_finished_v2.json. The interrupted C v1 is
retained separately, never relabeled as a completed arm. Models, reference and
evaluation evidence are independently checked in results/matrix_verification.json
and results/assessment/verification.json. Canonical outcome: reports/R121_RESULTS.md.
