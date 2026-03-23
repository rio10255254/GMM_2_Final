# GitHub Project Control Plane

This repository uses GitHub's server-side project and ruleset features as a
lightweight research governance layer.

## Rulesets

These JSON definitions are the intended source of truth for repository-level
protection:

- `ruleset-main.json`
  - protects `main`
  - blocks force pushes and deletion
  - requires pull-request based updates while still allowing the repository
    owner to bypass when necessary
- `ruleset-baseline.json`
  - protects `baseline/*`
  - preserves milestone branches as a reserved reference namespace
  - blocks ad-hoc creation and ordinary updates, while still allowing the
    repository owner to bypass when necessary

As of `2026-03-23`, these server-side rulesets have already been applied on
GitHub:

- `Protect main`
- `Protect baseline branches`

## Project

The intended GitHub Project title is:

- `GMM Research Control Plane`

Current status on `2026-03-23`:

- repository rulesets: applied on GitHub
- GitHub Project: created on GitHub
- project URL: `https://github.com/users/rio10255254/projects/1`
- current automation note: creating or updating Projects v2 by automation still
  requires a token with `project` / `read:project` scope

The project should visualize the current research path using the following
conceptual fields:

- `Track`
  - `baseline`
  - `reconstructed`
  - `research`
  - `sandbox`
- `Status`
  - `active`
  - `completed`
  - `falsified`
  - `promoted`
  - `archived`
- `External Verdict`
  - `pass`
  - `fail`
  - `pending`
  - `missing_artifact`
  - `n/a`
- `Branch`
- `Round`
- `Milestone Date`
  - ISO `YYYY-MM-DD`
  - a text reference field for quick sorting / reading
- `Start Date`
  - the actual GitHub Roadmap start-date field
- `Target Date`
  - the actual GitHub Roadmap target-date field

The current core timeline is intentionally kept to 10 high-value milestones:

1. `2026-03-07 | First usable baseline scaffold established`
2. `2026-03-09 | External GMF became the final gate`
3. `2026-03-11 | Round14 corridor identified 0.8px as the bottleneck`
4. `2026-03-12 | Round15 center-lock narrowed the target`
5. `2026-03-14 | Round20 process probe falsified the baseline-lock hypothesis`
6. `2026-03-17 | R26 sm035 confirmed as the generic step_mag optimum`
7. `2026-03-18 | Round30 architecture breakthrough promoted r30_b1_dironly`
8. `2026-03-19 | Round31 B1 hyperparameter tuning regressed externally`
9. `2026-03-20 | Round32 sandbox winner failed external compare`
10. `2026-03-20 | Post-R32 new sandbox branch is required`

These items are date-prefixed and also carry:

- `Milestone Date` for text sorting / quick reading
- `Start Date` / `Target Date` for the actual GitHub `Roadmap` layout

If the Project is opened in table view, `Milestone Date` is the easiest quick
sort key. If the Project is opened in roadmap view, GitHub uses `Start Date` and
`Target Date`.

The Project is for the **timeline**. The repository evidence chain itself should
be read through `docs/evidence/EVIDENCE_MAP.md`, which explains which curated
files support each baseline, falsified line, side-direction rejection, analysis
conclusion, and runtime truth snapshot.

## Manual Unblock For Future Project Automation

To create or modify the GitHub Project from automation in future sessions, the
token used on this machine must include the `project` scope. The current project
already exists; the extra scope is only required for future automated changes.

## Sync Rule

Only sync the following to GitHub:

- major branch creation
- strategy attempts with meaningful design changes
- important analyses and decision memos
- baseline / verdict changes
- governance and documentation updates

Do not sync day-to-day runtime noise, bulk logs, artifacts, or reproducible
payloads into Git history.
