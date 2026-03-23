param(
    [string]$OutputDir = "",
    [string]$CodexHome = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $PSScriptRoot "portable-bundle"
}

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Join-Path $env:USERPROFILE ".codex"
}

$PackageRoot = Split-Path -Parent $PSCommandPath
$ScriptsSource = Join-Path $PackageRoot "scripts"
$StateDir = Join-Path $OutputDir "state"
$ScriptsDir = Join-Path $OutputDir "scripts"
$SkillsDir = Join-Path $OutputDir "skills"
$TemplatesDir = Join-Path $OutputDir "templates"
$DocsDir = Join-Path $OutputDir "docs"
$ZipPath = "$OutputDir.zip"
$CleanOutputDir = Join-Path $PSScriptRoot "portable-clean-bundle"
$CleanScriptsDir = Join-Path $CleanOutputDir "scripts"
$CleanSkillsDir = Join-Path $CleanOutputDir "skills"
$CleanTemplatesDir = Join-Path $CleanOutputDir "templates"
$CleanDocsDir = Join-Path $CleanOutputDir "docs"
$CleanZipPath = "$CleanOutputDir.zip"

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Copy-IfExists {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        return
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
        return
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

function Write-RedactedConfig {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if (-not (Test-Path -LiteralPath $SourcePath)) {
        return
    }

    $content = Get-Content -LiteralPath $SourcePath -Raw -Encoding UTF8
    $content = [regex]::Replace($content, '(?im)^(experimental_bearer_token\s*=\s*").*(")$', '$1REPLACE_ME$2')
    $content = [regex]::Replace($content, '(?im)^(OPENAI_API_KEY\s*=\s*").*(")$', '$1REPLACE_ME$2')

    $destinationParent = Split-Path -Parent $DestinationPath
    if ($destinationParent) {
        Ensure-Directory -Path $destinationParent
    }

    Set-Content -LiteralPath $DestinationPath -Value $content -Encoding UTF8
}

if (Test-Path -LiteralPath $OutputDir) {
    Remove-Item -LiteralPath $OutputDir -Recurse -Force
}
if (Test-Path -LiteralPath $CleanOutputDir) {
    Remove-Item -LiteralPath $CleanOutputDir -Recurse -Force
}

Ensure-Directory -Path $OutputDir
Ensure-Directory -Path $StateDir
Ensure-Directory -Path $ScriptsDir
Ensure-Directory -Path $SkillsDir
Ensure-Directory -Path $TemplatesDir
Ensure-Directory -Path $DocsDir
Ensure-Directory -Path $CleanOutputDir
Ensure-Directory -Path $CleanScriptsDir
Ensure-Directory -Path $CleanSkillsDir
Ensure-Directory -Path $CleanTemplatesDir
Ensure-Directory -Path $CleanDocsDir

Copy-IfExists -SourcePath (Join-Path $PackageRoot "bootstrap.ps1") -DestinationPath (Join-Path $OutputDir "bootstrap.ps1")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "verify.ps1") -DestinationPath (Join-Path $OutputDir "verify.ps1")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "INSTALL_PORTABLE_AGENT_ENV.cmd") -DestinationPath (Join-Path $OutputDir "INSTALL_PORTABLE_AGENT_ENV.cmd")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "manifest.json") -DestinationPath (Join-Path $OutputDir "manifest.json")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "README_ENV_SETUP.md") -DestinationPath (Join-Path $DocsDir "README_ENV_SETUP.md")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "templates\codex.config.portable.toml") -DestinationPath (Join-Path $TemplatesDir "codex.config.portable.toml")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "skills\portable-agent-env") -DestinationPath (Join-Path $SkillsDir "portable-agent-env")
Copy-DirectoryContents -SourcePath $ScriptsSource -DestinationPath $ScriptsDir
Collapse-NestedDirectory -Path $ScriptsDir

Copy-IfExists -SourcePath (Join-Path $PackageRoot "bootstrap.ps1") -DestinationPath (Join-Path $CleanOutputDir "bootstrap.ps1")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "verify.ps1") -DestinationPath (Join-Path $CleanOutputDir "verify.ps1")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "INSTALL_PORTABLE_AGENT_ENV.cmd") -DestinationPath (Join-Path $CleanOutputDir "INSTALL_PORTABLE_AGENT_ENV.cmd")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "manifest.json") -DestinationPath (Join-Path $CleanOutputDir "manifest.json")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "README_ENV_SETUP.md") -DestinationPath (Join-Path $CleanDocsDir "README_ENV_SETUP.md")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "templates\codex.config.portable.toml") -DestinationPath (Join-Path $CleanTemplatesDir "codex.config.portable.toml")
Copy-IfExists -SourcePath (Join-Path $PackageRoot "skills\portable-agent-env") -DestinationPath (Join-Path $CleanSkillsDir "portable-agent-env")
Copy-DirectoryContents -SourcePath $ScriptsSource -DestinationPath $CleanScriptsDir
Collapse-NestedDirectory -Path $CleanScriptsDir

Copy-IfExists -SourcePath (Join-Path $CodexHome "session_ai_titles.jsonl") -DestinationPath (Join-Path $StateDir "session_ai_titles.jsonl")
Write-RedactedConfig -SourcePath (Join-Path $CodexHome "config.toml") -DestinationPath (Join-Path $StateDir "codex.config.redacted.toml")
Copy-IfExists -SourcePath (Join-Path $CodexHome "rules\default.rules") -DestinationPath (Join-Path $StateDir "default.rules.snapshot")
Copy-IfExists -SourcePath (Join-Path $env:USERPROFILE "Documents\PowerShell\Microsoft.PowerShell_profile.ps1") -DestinationPath (Join-Path $StateDir "pwsh_profile.current.ps1")
Copy-IfExists -SourcePath (Join-Path $env:USERPROFILE "Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1") -DestinationPath (Join-Path $StateDir "windows_powershell_profile.current.ps1")

$summary = @{
    exported_at = [datetime]::UtcNow.ToString("o")
    source_codex_home = $CodexHome
    bundle_root = $OutputDir
    files = @(
        "bootstrap.ps1",
        "verify.ps1",
        "INSTALL_PORTABLE_AGENT_ENV.cmd",
        "manifest.json",
        "docs/README_ENV_SETUP.md",
        "templates/codex.config.portable.toml",
        "scripts/Invoke-CodexWithHome.ps1",
        "scripts/Get-CodexHomeStatus.ps1",
        "scripts/codex_resume_all.ps1",
        "scripts/verify_codex_entrypoints.ps1",
        "scripts/testdata/noop.cmd",
        "skills/portable-agent-env/SKILL.md",
        "state/session_ai_titles.jsonl",
        "state/codex.config.redacted.toml",
        "state/default.rules.snapshot"
    )
    secrets_included = $false
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputDir "export-summary.json") -Encoding UTF8

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $OutputDir "*") -DestinationPath $ZipPath -Force

$cleanSummary = @{
    exported_at = [datetime]::UtcNow.ToString("o")
    bundle_root = $CleanOutputDir
    bundle_type = "clean-install"
    files = @(
        "bootstrap.ps1",
        "verify.ps1",
        "INSTALL_PORTABLE_AGENT_ENV.cmd",
        "manifest.json",
        "docs/README_ENV_SETUP.md",
        "templates/codex.config.portable.toml",
        "scripts/Invoke-CodexWithHome.ps1",
        "scripts/Get-CodexHomeStatus.ps1",
        "scripts/codex_resume_all.ps1",
        "scripts/verify_codex_entrypoints.ps1",
        "scripts/testdata/noop.cmd",
        "skills/portable-agent-env/SKILL.md"
    )
    includes_machine_specific_state = $false
}
$cleanSummary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $CleanOutputDir "export-summary.json") -Encoding UTF8

if (Test-Path -LiteralPath $CleanZipPath) {
    Remove-Item -LiteralPath $CleanZipPath -Force
}
Compress-Archive -Path (Join-Path $CleanOutputDir "*") -DestinationPath $CleanZipPath -Force

Write-Host "Portable bundle exported."
Write-Host "Bundle root: $OutputDir"
Write-Host "Zip package: $ZipPath"
Write-Host "Clean bundle root: $CleanOutputDir"
Write-Host "Clean zip package: $CleanZipPath"
Write-Host "Next step: copy the clean zip or clean folder to another machine and run INSTALL_PORTABLE_AGENT_ENV.cmd"
