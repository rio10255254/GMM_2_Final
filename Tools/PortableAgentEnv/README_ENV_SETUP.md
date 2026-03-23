# Portable Agent Environment

## 目的 / Purpose

這個套件把目前的 Codex / PowerShell 個人化環境整理成一個可攜式工作站組件。  
This package turns the current Codex / PowerShell personalization into a portable workstation kit.

它的目標是：  
Its goals are:

- keep the current machine reproducible  
  保持目前工作站可重現
- let a new machine install the same terminal behavior quickly  
  讓新機器能快速裝回同樣的終端機行為
- let another AI agent read one place and follow the same setup  
  讓其他 AI agent 能從單一入口理解並複製同樣設定

## 這個套件涵蓋什麼 / What This Package Covers

- PowerShell profile wrapper for `codex resume --all`
- full on-disk Codex session listing
- persistent AI-generated short session titles
- portable install root for helper scripts
- optional installation of a Codex skill that explains setup and repair
- redacted config and current state export for migration

## 不會自動搬移的東西 / What This Package Does Not Auto-Migrate

- API keys
- provider bearer tokens
- Telegram bot token
- machine-specific scheduled tasks
- machine-specific approval history

這些故意保留為手動處理。  
These items remain manual on purpose.

## 資料夾結構 / Folder Layout

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

當你執行 `export-current-state.ps1` 時，會另外產生一個可攜式 bundle，包含：  
When you run `export-current-state.ps1`, it also creates a standalone migration bundle containing:

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

## 建議搬移流程 / Recommended Migration Workflow

### 在目前機器上 / On the Current Machine

1. Run `export-current-state.ps1`
2. Copy the exported bundle to the new machine
3. Manually add secrets on the new machine

### 在新機器上 / On the New Machine

1. Install PowerShell and Codex CLI
2. Put the exported bundle anywhere convenient
3. Double-click `INSTALL_PORTABLE_AGENT_ENV.cmd` or run `bootstrap.ps1`
4. Update `~/.codex/config.toml` with valid provider/auth settings
5. Run `verify.ps1`

## 目前機器安裝方式 / Current Machine Install

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

## 驗證 / Verify

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

## 匯出 / Export

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

## 關於 Telegram Bridge / Notes About Telegram Bridge

Telegram bridge 被視為可選的附加元件。  
Telegram bridge is treated as an optional companion component.

這個套件不會自動安裝 bridge，因為它需要：  
This package does not auto-install the bridge because it depends on:

- Telegram token
- chat routing choices
- scheduled task decisions

如果需要，請用它自己的 installer 個別搬移，再讓它指向同一個 `~/.codex` home。  
If needed, migrate the bridge separately with its own installer and then point it at the same `~/.codex` home.

## 維護規則 / Operational Rule

For future maintenance:

- keep environment behavior in this package
- keep repo-specific workflow scripts in the repo
- keep secrets out of versioned files
