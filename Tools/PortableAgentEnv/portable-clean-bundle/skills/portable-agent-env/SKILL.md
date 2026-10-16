---
name: portable-agent-env
description: Use when setting up, migrating, verifying, or repairing Rio's portable Codex and PowerShell workstation environment on Windows. Covers bootstrap, verification, exported state import, profile wrappers, and the full-session `codex resume --all` behavior.
---

# Portable Agent Environment

Use this skill when the task is to install, migrate, verify, or repair the portable Codex workstation setup.

## Entry Points

- Install: `bootstrap.ps1`
- Verify: `verify.ps1`
- Export/migrate: `export-current-state.ps1`
- Human docs: `README_ENV_SETUP.md`
- Package metadata: `manifest.json`

## Working Rules

- Treat this package as the canonical source for workstation customization.
- Do not hardcode secrets into package files.
- Preserve user profile content outside the managed block.
- Prefer importing cached AI session titles instead of regenerating old titles.
- If another machine is missing local sessions, do not assume they can be recreated from this package alone.

## Standard Flow

### New machine setup

1. Read `README_ENV_SETUP.md`.
2. Run `bootstrap.ps1`.
3. Ensure the user manually configures valid provider/auth settings in `~/.codex/config.toml`.
4. Run `verify.ps1`.
5. Confirm `codex resume --all` now uses the full on-disk session helper.

### Migration from an existing machine

1. Run `export-current-state.ps1` on the source machine.
2. Copy the exported bundle to the destination machine.
3. Run `bootstrap.ps1 -ImportStateDir .\state`.
4. Run `verify.ps1`.

### Repair flow

1. Check both profile files still contain the `portable-agent-env` managed block.
2. Check the installed helper exists under the install root.
3. Check the skill exists under `~/.codex/skills/portable-agent-env`.
4. Check `session_ai_titles.jsonl` exists and has entries.
5. Re-run `bootstrap.ps1` if any of the above drifted.

## Important Caveats

- `session_ai_titles.jsonl` is portable metadata, not the session history itself.
- Telegram bridge is an optional companion and must be migrated separately.
- Rules snapshots are exported for reference; do not blindly reapply machine-specific approval rules.
