# Project Working Rules

You are an AI coding agent working in this repository.

Before planning or summarizing current state, read:

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`

## Primary role

The agent may analyze requirements, edit files, run shell commands, and verify results directly in this repository.

## Tooling policy

- Prefer direct work in the current session.
- Do not assume any external delegation tool is available.
- Only use external delegation when the user explicitly asks for it and the tool is confirmed to exist.
- If an external delegation path is unavailable, continue the task directly instead of blocking.

## Execution standards

- Keep changes scoped to the request.
- Run relevant checks before reporting completion.
- Summarize the outcome with enough detail for the user to understand what changed and why; call out any remaining risks.

## Experiment conventions (MUST follow)

When creating a new experiment:

1. **Read first**: `docs/index/NAMING_CONVENTIONS.md` for naming rules, `docs/index/EXPERIMENT_TEMPLATE.md` for structure template.
2. **Directory**: `Experiments/R##_Description/` with `README.md` + `scripts/` + `reports/` + `results/`.
3. **Launcher**: Must include `trainer.MODEL_NAME_BASE = CFG.MODEL_NAME` to ensure artifact identity.
4. **Branch**: `sandbox/r##` from the appropriate base branch.
5. **Reports**: `R##_TYPE.md` format (RESULTS / SUMMARY / AUDIT / METHODOLOGY).
6. **External GMF**: Raw step_std (no outlier removal except z > 5 GMF failures). See `Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`.
7. **Sequence analysis**: Uses 720-angle sampling (not 360).
8. **After completion**: Add entry to `Experiments/INDEX.md` and create `MANIFEST.md` in the experiment directory.

## Documentation update policy

When recording experiment results, update ALL of:
- `ESTIMATOR_POLICY.json` (external compare + notes)
- `PROJECT_CURRENT_STATE.md` (results section)
- `PROJECT_SESSION_CONTINUITY.md` (handoff snapshot)
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` (findings + cautions)
- `docs/analysis/RESEARCH_PATHS.md` (flowchart + milestone table)
- `docs/evidence/EVIDENCE_MAP.md` (evidence pointers)
- `Experiments/INDEX.md` (experiment index)

## Known quirks

Read `docs/index/QUIRKS_AND_CONVENTIONS.md` before making changes that touch:
- `Traing_Progress/` (intentional typo, do not rename)
- `Training_Data/` (gitignored but has tracked Python scripts)
- Model/ directory (flat structure is intentional)
- External GMF outlier methods (different scripts use different rules)
