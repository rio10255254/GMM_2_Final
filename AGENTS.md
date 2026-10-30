# Project Working Rules

You are an AI coding agent working in this repository.

Before planning or summarizing current state, read:

1. `PROJECT_STATE.md`

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
- It helps for new code to find the project root from its own location (for example `Path(__file__).resolve().parents[N]`) rather than naming a drive path, so the project keeps working from any folder or machine.

## Experiment conventions (MUST follow)

When creating a new experiment:

1. **Read first**: `docs/operations/STARTING_NEW_EXPERIMENT.md` — the full guide (naming rules, directory template, SOP steps).
2. **Directory**: `Experiments/R##_Description/` with `README.md` + `scripts/` + `reports/` + `results/`.
3. **Launcher**: Must include `trainer.MODEL_NAME_BASE = CFG.MODEL_NAME` to ensure artifact identity.
4. **Branch**: `sandbox/r##` from the appropriate base branch.
5. **Reports**: `R##_TYPE.md` format (RESULTS / SUMMARY / AUDIT / METHODOLOGY).
6. **External GMF**: Raw step_std (no outlier removal except z > 5 GMF failures). See `Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`.
7. **Sequence analysis**: Uses 720-angle sampling (not 360).
8. **After completion**: Add entry to `Experiments/INDEX.md` and create `MANIFEST.md` in the experiment directory.

## Documentation update policy

When recording experiment results, update these **5 mandatory files**:
- `ESTIMATOR_POLICY.json` (external compare + notes)
- `PROJECT_STATE.md` (Quick Handoff region + relevant Full Current State section)
- `PROJECT_ARCHITECTURE.md` (only if stable rules changed)
- `Experiments/INDEX.md` (experiment index)
- The relevant experiment's `reports/` canonical file

**Optional** (no longer mandatory; update when it helps readers):
- `docs/analysis/RESEARCH_PATHS.md` — update flowchart when a line is promoted/closed
- `docs/evidence/EVIDENCE_MAP.md` — update evidence pointers when canonical reports move
- `docs/evidence/*` mirrors — may drift from canonical; canonical is authoritative
- `RECON_GALLERY.md` (repo root) — add a section with representative recon BMPs + metric plots when a new round produces visual output. **Must stay pure markdown** (no `<table>`, `<p>`, `<details>`, `<img>`, `<div>`, `<a href>`). Enforced by `check_recon_gallery_format()` in the validator.

## Source of truth policy

Read `docs/operations/SOURCE_OF_TRUTH_POLICY.md` before editing any file that might have copies elsewhere.
- For R33+ experiments, `Experiments/*/reports/` is the only editable location for experiment reports
- `docs/evidence/` contains curated copies used as stable citation anchors — may drift from canonical; canonical is authoritative
- `Model/GeoEdgeAlignSR_v1_Infer_v5_*.py` is canonical; deployment/package copies must be synced manually
- For legacy batches under `Experiments/Legacy/organized_20260313-20260316/`, use `docs/operations/LEGACY_ROUNDS_OPERATIONS.md` before editing legacy surfaces
- When in doubt about which copy is canonical, check the policy file or ask the user

## Known quirks

Read `docs/operations/QUIRKS.md` before making changes that touch:
- `Experiments/Legacy/` and `Experiments/Training_Runs/` (the root `Traing_Progress` folder, split on 2026-10-28; old reports and logs still name it)
- `Training_Data/` (gitignored but has tracked Python scripts)
- Model/ directory (flat structure is intentional)
- External GMF outlier methods (different scripts use different rules)
