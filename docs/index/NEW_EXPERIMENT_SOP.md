# New Experiment SOP

Use this checklist whenever you want to add a new experiment or research line.

## 1. Choose the right branch family

- Use `research/*` for new strategy attempts, tuning lines, or analysis-driven follow-up work.
- Use `sandbox/*` for isolated execution surfaces that should not be treated as baseline candidates yet.
- Do **not** use `baseline/*` for new work. That namespace is reserved for approved baseline milestones only.

## 2. Create the branch

- Start from `main`.
- Name the branch to match the work:
  - `research/<round-or-topic>`
  - `sandbox/<round-or-topic>`

## 3. Open the tracking issue

- Use the existing issue template:
  - `.github/ISSUE_TEMPLATE/research-round-proposal.yml`
- In that issue, capture:
  - round / branch name
  - hypothesis
  - comparison target
  - success condition
  - expected external verdict path

## 4. Update the GitHub Project

Open `GMM Research Control Plane` and add or update an item with:

- `Track`
- `Research Status`
- `External Verdict`
- `Branch`
- `Round`
- `Milestone Date`
- `Start Date`
- `Target Date`

Use:

- `Research Status = active` when the line is live
- `External Verdict = pending` until external compare is confirmed

## 5. Update formal docs only when truth changes

Update these docs when the work crosses a formal boundary:

- `PROJECT_CURRENT_STATE.md`
  - when current truth, adopted baseline, or next decision boundary changes
- `PROJECT_SESSION_CONTINUITY.md`
  - when handoff truth or canonical entry points change
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
  - when stable rules or branch/governance policy change

Do not update canonical docs for day-to-day runtime noise.

## 6. Open a PR

- Keep the PR limited to tracked source, docs, or governance files.
- Use `.github/PULL_REQUEST_TEMPLATE.md`.

## 7. Trigger Codex review manually for non-trivial PRs

For any non-trivial PR, after opening it or marking it ready for review, leave:

`@codex review`

If Codex leaves actionable comments, follow up in the PR with:

`@codex address that feedback`

## 8. Merge only after the line is clear

- `main` and `baseline/*` are protected.
- New experiment work should merge through PR, not direct pushes.
- Keep bulk artifacts, logs, weights, reconstructions, and runtime noise out of Git.
