# R128 使用與執行

This experiment is self-contained. Use C:\Users\Rio\anaconda3\python.exe and run from the experiment root. The training runner records explicit arm/seed identities; it does not modify the shared legacy trainer or model-name globals.

## Preparation and first start

1. scripts/common.py protects previous evidence and preserves the project context. Run once only.
2. scripts/build_data.py creates the preassigned 512/128/128 bank. Existing attempts are refused, not replaced.
3. scripts/preflight.py executes model/operator/context/learning/recovery checks and retains each attempt.
4. scripts/prepare_real.py establishes exact fresh initializations and executes the complete Raw real panel.
5. scripts/run_integration.py runs the same complete real evaluator with a nonneutral engineering-smoke model.
6. scripts/check_training_data.py checks the actual consumer, new noise, source isolation, physical supervision and arm-gradient contrast.
7. scripts/freeze_study.py verifies current code equals tested code, checks protected history and freezes the full schedule.
8. scripts/coordinator.py runs I/P for seed1285001, then I/P for seed1285002.

The live record is runs/launcher_logs/active_formal_run.json. Actual update ledgers, resumable immutable checkpoints, per-checkpoint evaluations and completion records reside under runs/I_s1285001 and the three analogous run folders. A process, status marker or checksum alone is not scientific completion.

## Recovery

Latest continuation2026-09-09 17:12: launch recovery/20260909_external_stop/independent_entry.py as a one-off hidden Windows-service-parented process outside the application job, as tested and recorded in that directory. It invokes the same unchanged recovery coordinator below and skips verified completed runs. Direct launch from an application-managed job is intentionally refused. Preserve any stale coordinator lock only after verifying both old processes are absent. See R128_RUNTIME_CHECK_20260909.md for the second interruption and exact replay evidence.

Inspect the coordinator and child PIDs, last status, stderr, last checkpoint hash and update ledger together. Never remove a possibly active lock. If a coordinator crashed, preserve its lock by renaming it only after verifying that both coordinator and child have stopped. The active replacement runner is recovery/20260909_progress_io_v1/coordinate.py; it resumes unfinished runs automatically and validates completed output identities. Do not restart the original unpatched coordinator: its progress I/O failed after update1393. The original frozen code remains intact and is called through the explicitly recorded I/O adapter. See R128_RECOVERY_20260909.md and the separate recovery manifest.

A partial evaluation directory is intentionally refused. Preserve it under a separately named failed-attempt directory after inspecting the cause, then rerun the same frozen checkpoint. Do not alter source identities, admission limits or previously written outputs.

Final step8192 is the primary checkpoint. Development results are diagnostics, not a best-step selector. The generated test is allowed only at8192. The sole old144-scene confirmation is not used by any R128 path.
