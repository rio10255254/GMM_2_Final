param(
    [string]$InstallRoot = "",
    [string]$CodexHome = "",
    [string]$ImportStateDir = "",
    [switch]$InstallSkill = $true,
    [switch]$InstallProfiles = $true,
    [switch]$InstallConfigTemplate = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $InstallRoot = Join-Path $env:USERPROFILE ".portable-agent-env"
}

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Join-Path $env:USERPROFILE ".codex"
}

$PackageRoot = Split-Path -Parent $PSCommandPath
$ScriptsSourceRoot = Join-Path $PackageRoot "scripts"
$ScriptsTargetRoot = Join-Path $InstallRoot "scripts"
$ResumeHelperTarget = Join-Path $ScriptsTargetRoot "codex_resume_all.ps1"
$InvokeHelperTarget = Join-Path $ScriptsTargetRoot "Invoke-CodexWithHome.ps1"
$StatusHelperTarget = Join-Path $ScriptsTargetRoot "Get-CodexHomeStatus.ps1"
$DocsTarget = Join-Path $InstallRoot "docs"
$TemplatesTarget = Join-Path $InstallRoot "templates"
$SkillSource = Join-Path $PackageRoot "skills\portable-agent-env"
$SkillTarget = Join-Path $CodexHome "skills\portable-agent-env"
$ConfigTemplateSource = Join-Path $PackageRoot "templates\codex.config.portable.toml"
$ConfigTemplateTarget = Join-Path $InstallRoot "templates\codex.config.portable.toml"
$InstallStatePath = Join-Path $InstallRoot "install-state.json"

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Copy-Path {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        throw "Required source path not found: $SourcePath"
    }

    $destinationParent = Split-Path -Parent $DestinationPath
    if ($destinationParent) {
        Ensure-Directory -Path $destinationParent
    }

    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force -Recurse
}

function Copy-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        throw "Required source path not found: $SourcePath"
    }

    Ensure-Directory -Path $DestinationPath

    foreach ($item in Get-ChildItem -LiteralPath $SourcePath -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $DestinationPath $item.Name) -Force -Recurse
    }
}

function Collapse-NestedDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $leaf = Split-Path -Leaf $Path
    $nestedPath = Join-Path $Path $leaf
    if (-not (Test-Path -LiteralPath $nestedPath)) {
        return
    }

    foreach ($item in Get-ChildItem -LiteralPath $nestedPath -Force) {
        Move-Item -LiteralPath $item.FullName -Destination (Join-Path $Path $item.Name) -Force
    }

    Remove-Item -LiteralPath $nestedPath -Recurse -Force
}

function Upsert-ManagedProfileBlock {
    param(
        [Parameter(Mandatory = $true)][string]$ProfilePath,
        [Parameter(Mandatory = $true)][string]$ScriptsRoot,
        [Parameter(Mandatory = $true)][string]$OpenAiCodexHome
    )

    $markerStart = "# >>> portable-agent-env >>>"
    $markerEnd = "# <<< portable-agent-env <<<"
    $scriptsRootLiteral = $ScriptsRoot.Replace("'", "''")
    $openAiHomeLiteral = $OpenAiCodexHome.Replace("'", "''")
    $block = @"
$markerStart
function Get-CodexHelperPath {
    param(
        [Parameter(Mandatory = `$true)]
        [string]`$Leaf
    )

    `$scriptsRoot = '$scriptsRootLiteral'
    return Join-Path `$scriptsRoot `$Leaf
}

function Invoke-CodexPinnedHome {
    param(
        [Parameter(Mandatory = `$true)]
        [string]`$CodexHome,

        [Parameter(ValueFromRemainingArguments = `$true)]
        [string[]]`$Args
    )

    `$invokeScript = Get-CodexHelperPath -Leaf 'Invoke-CodexWithHome.ps1'

    if (-not (Test-Path -LiteralPath `$invokeScript)) {
        throw "Codex home wrapper not found: `$invokeScript"
    }

    & `$invokeScript -CodexHome `$CodexHome -RawArgs `$Args
}

function codex {
    param(
        [Parameter(ValueFromRemainingArguments = `$true)]
        [string[]]`$Args
    )

    `$yunyiHome = Join-Path `$env:USERPROFILE '.codex-yunyi'
    Invoke-CodexPinnedHome -CodexHome `$yunyiHome -Args `$Args
}

function codex-yunyi {
    param(
        [Parameter(ValueFromRemainingArguments = `$true)]
        [string[]]`$Args
    )

    `$yunyiHome = Join-Path `$env:USERPROFILE '.codex-yunyi'
    Invoke-CodexPinnedHome -CodexHome `$yunyiHome -Args `$Args
}

function codex-openai {
    param(
        [Parameter(ValueFromRemainingArguments = `$true)]
        [string[]]`$Args
    )

    `$openaiHome = '$openAiHomeLiteral'
    Invoke-CodexPinnedHome -CodexHome `$openaiHome -Args `$Args
}

function codex-status {
    `$statusScript = Get-CodexHelperPath -Leaf 'Get-CodexHomeStatus.ps1'
    if (-not (Test-Path -LiteralPath `$statusScript)) {
        throw "Codex status helper not found: `$statusScript"
    }

    `$openaiHome = '$openAiHomeLiteral'
    `$yunyiHome = Join-Path `$env:USERPROFILE '.codex-yunyi'

    Write-Host 'default terminal codex -> yunyi' -ForegroundColor Cyan
    & `$statusScript -CodexHome `$yunyiHome | Format-List
    & `$statusScript -CodexHome `$openaiHome | Format-List
}
$markerEnd
"@

    $profileDir = Split-Path -Parent $ProfilePath
    Ensure-Directory -Path $profileDir

    $content = ""
    if (Test-Path -LiteralPath $ProfilePath) {
        $content = Get-Content -LiteralPath $ProfilePath -Raw -Encoding UTF8
    }

    $escapedStart = [regex]::Escape($markerStart)
    $escapedEnd = [regex]::Escape($markerEnd)
    $pattern = "(?ms)^$escapedStart.*?^$escapedEnd\s*"
    if ($content -match $pattern) {
        $content = [regex]::Replace($content, $pattern, $block + [Environment]::NewLine)
    } elseif ([string]::IsNullOrWhiteSpace($content)) {
        $content = $block + [Environment]::NewLine
    } else {
        $content = $content.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $block + [Environment]::NewLine
    }

    Set-Content -LiteralPath $ProfilePath -Value $content -Encoding UTF8
}

function Merge-JsonlBySessionId {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        return
    }

    $map = @{}
    foreach ($path in @($DestinationPath, $SourcePath)) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }

        foreach ($raw in Get-Content -LiteralPath $path -Encoding UTF8) {
            try {
                $payload = $raw | ConvertFrom-Json
            } catch {
                continue
            }

            $sessionId = [string]$payload.session_id
            if (-not [string]::IsNullOrWhiteSpace($sessionId)) {
                $map[$sessionId] = $payload
            }
        }
    }

    $destinationParent = Split-Path -Parent $DestinationPath
    if ($destinationParent) {
        Ensure-Directory -Path $destinationParent
    }

    $lines = foreach ($entry in $map.GetEnumerator() | Sort-Object Name) {
        $entry.Value | ConvertTo-Json -Depth 8 -Compress
    }
    Set-Content -LiteralPath $DestinationPath -Value $lines -Encoding UTF8
}

Ensure-Directory -Path $InstallRoot
Ensure-Directory -Path $ScriptsTargetRoot
Ensure-Directory -Path $DocsTarget
Ensure-Directory -Path $TemplatesTarget
Ensure-Directory -Path $CodexHome

Copy-DirectoryContents -SourcePath $ScriptsSourceRoot -DestinationPath $ScriptsTargetRoot
Collapse-NestedDirectory -Path $ScriptsTargetRoot
Copy-Path -SourcePath (Join-Path $PackageRoot "manifest.json") -DestinationPath (Join-Path $InstallRoot "manifest.json")
Copy-Path -SourcePath (Join-Path $PackageRoot "README_ENV_SETUP.md") -DestinationPath (Join-Path $DocsTarget "README_ENV_SETUP.md")

if ($InstallConfigTemplate) {
    Copy-Path -SourcePath $ConfigTemplateSource -DestinationPath $ConfigTemplateTarget
    Copy-Path -SourcePath $ConfigTemplateSource -DestinationPath (Join-Path $CodexHome "config.portable.example.toml")
}

if ($InstallSkill) {
    if (Test-Path -LiteralPath $SkillTarget) {
        Remove-Item -LiteralPath $SkillTarget -Force -Recurse
    }
    Copy-Path -SourcePath $SkillSource -DestinationPath $SkillTarget
}

if ($InstallProfiles) {
    Upsert-ManagedProfileBlock -ProfilePath (Join-Path $env:USERPROFILE "Documents\PowerShell\Microsoft.PowerShell_profile.ps1") -ScriptsRoot $ScriptsTargetRoot -OpenAiCodexHome $CodexHome
    Upsert-ManagedProfileBlock -ProfilePath (Join-Path $env:USERPROFILE "Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1") -ScriptsRoot $ScriptsTargetRoot -OpenAiCodexHome $CodexHome
}

if (-not [string]::IsNullOrWhiteSpace($ImportStateDir) -and (Test-Path -LiteralPath $ImportStateDir)) {
    Merge-JsonlBySessionId `
        -SourcePath (Join-Path $ImportStateDir "session_ai_titles.jsonl") `
        -DestinationPath (Join-Path $CodexHome "session_ai_titles.jsonl")

    if (Test-Path -LiteralPath (Join-Path $ImportStateDir "codex.config.redacted.toml")) {
        Copy-Path `
            -SourcePath (Join-Path $ImportStateDir "codex.config.redacted.toml") `
            -DestinationPath (Join-Path $InstallRoot "state\codex.config.redacted.toml")
    }
}

$installState = @{
    installed_at = [datetime]::UtcNow.ToString("o")
    install_root = $InstallRoot
    codex_home = $CodexHome
    scripts_source = $ScriptsSourceRoot
    helper_target = $InvokeHelperTarget
    resume_helper_target = $ResumeHelperTarget
    status_helper_target = $StatusHelperTarget
    skill_installed = [bool]$InstallSkill
    profiles_installed = [bool]$InstallProfiles
    config_template_installed = [bool]$InstallConfigTemplate
    import_state_dir = $ImportStateDir
}
$installState | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $InstallStatePath -Encoding UTF8

Write-Host "Portable agent environment installed."
Write-Host "Install root: $InstallRoot"
Write-Host "Codex home: $CodexHome"
Write-Host "Helper: $InvokeHelperTarget"
Write-Host "Next step: run verify.ps1"
