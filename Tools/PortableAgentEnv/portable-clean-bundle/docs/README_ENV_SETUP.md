# Portable Agent Environment

## Purpose

This package turns the current Codex/PowerShell personalization into a movable workstation kit.

The goal is:

- keep the current machine reproducible
- let a new machine install the same terminal behavior quickly
- let another AI agent read one place and follow the same setup

## What This Package Covers

- PowerShell profile wrapper for `codex resume --all`
- full on-disk Codex session listing
- persistent AI-generated short session titles
- portable install root for helper scripts
- optional installation of a Codex skill that explains setup and repair
- redacted config and current state export for migration

## What This Package Does Not Auto-Migrate

- API keys
- provider bearer tokens
- Telegram bot token
- machine-specific scheduled tasks
- machine-specific approval history

Those stay manual on purpose.

## Folder Layout

```text
PortableAgentEnv/
  bootstrap.ps1
  verify.ps1
  export-current-state.ps1
  manifest.json
  README_ENV_SETUP.md
  templates/
    codex.config.portable.toml
  skills/
    portable-agent-env/
      SKILL.md
```

When you run `export-current-state.ps1`, it creates a standalone bundle that also contains:

```text
scripts/
  codex_resume_all.ps1
state/
  session_ai_titles.jsonl
  codex.config.redacted.toml
  pwsh_profile.current.ps1
  windows_powershell_profile.current.ps1
  default.rules.snapshot
```

## Recommended Migration Workflow

### On the current machine

1. Run `export-current-state.ps1`
2. Copy the exported bundle to the new machine
3. Manually add secrets on the new machine

### On the new machine

1. Install PowerShell and Codex CLI
2. Put the exported bundle anywhere convenient
3. Double-click `INSTALL_PORTABLE_AGENT_ENV.cmd` or run `bootstrap.ps1`
4. Update `~/.codex/config.toml` with valid provider/auth settings
5. Run `verify.ps1`

## Current Machine Install

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tools\PortableAgentEnv\bootstrap.ps1
```

Or simply double-click:

```text
INSTALL_PORTABLE_AGENT_ENV.cmd
```

Default install root:

```text
C:\Users\<USER>\.portable-agent-env
```

Default Codex home:

```text
C:\Users\<USER>\.codex
```

The installer:

- copies helper/docs/templates into the install root
- updates both PowerShell profile files with a managed `codex` wrapper block
- installs the `portable-agent-env` skill into `~/.codex/skills`
- optionally imports state files from an exported bundle

## Verify

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tools\PortableAgentEnv\verify.ps1
```

The verifier checks:

- install root exists
- helper script exists
- both profile files contain the managed wrapper
- `codex` resolves as a function in both `pwsh` and `powershell.exe`
- skill install exists
- AI title cache exists and reports line count

## Export

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\Tools\PortableAgentEnv\export-current-state.ps1
```

This creates a standalone migration bundle under:

```text
.\Tools\PortableAgentEnv\portable-bundle
```

And also creates a zip package:

```text
.\Tools\PortableAgentEnv\portable-bundle.zip
```

## Notes About Telegram Bridge

Telegram bridge is treated as an optional companion component.

This package does not auto-install the bridge because it needs:

- Telegram token
- chat routing choices
- scheduled task decisions

If needed, migrate the bridge separately with its own installer and then point it at the same `~/.codex` home.

## Operational Rule

For future maintenance:

- keep environment behavior in this package
- keep repo-specific workflow scripts in the repo
- keep secrets out of versioned files
