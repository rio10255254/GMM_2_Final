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
  - preserves milestone branches as reference branches

As of `2026-03-23`, these server-side rulesets have already been applied on
GitHub:

- `Protect main`
- `Protect baseline branches`

## Project

The intended GitHub Project title is:

- `GMM Research Control Plane`

Current status on `2026-03-23`:

- repository rulesets: applied on GitHub
- GitHub Project: not yet created via API because the available token only has
  `gist`, `repo`, and `workflow` scopes, and GitHub Projects v2 creation
  requires the `project` scope

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

Initial project items should at minimum include:

1. `Round30 / r30_b1_dironly` as the current production baseline
2. `Round31` as a measured external regression line
3. `Round32 / r32_real_eq_finetune` as an externally falsified sandbox line
4. `R32 post-falsification` as the next required new branch / mechanism

## Manual Unblock For Project Creation

To create and manage the GitHub Project from automation, the token used on this
machine must include the `project` scope. Once that is available, create the
project with the title above and populate it using the field and item model in
this file.

## Sync Rule

Only sync the following to GitHub:

- major branch creation
- strategy attempts with meaningful design changes
- important analyses and decision memos
- baseline / verdict changes
- governance and documentation updates

Do not sync day-to-day runtime noise, bulk logs, artifacts, or reproducible
payloads into Git history.
