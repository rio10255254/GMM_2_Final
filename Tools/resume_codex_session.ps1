param(
    [Parameter(Mandatory = $true)]
    [string]$SessionId,

    [string]$WorkingDirectory = (Get-Location).Path,

    [string]$SourceCodexHome = "",

    [string]$TargetCodexHome = "",

    [switch]$UseProjectRuntime,

    [switch]$CopyAllSessions,

    [switch]$SkipLaunch,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CodexArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($SourceCodexHome)) {
    $SourceCodexHome = Join-Path $env:USERPROFILE ".codex"
}

if ([string]::IsNullOrWhiteSpace($TargetCodexHome)) {
    if ($UseProjectRuntime) {
        $TargetCodexHome = Join-Path (Split-Path $PSScriptRoot -Parent) ".codex_runtime"
    } else {
        $TargetCodexHome = $SourceCodexHome
    }
}

$sourceFullPath = [System.IO.Path]::GetFullPath($SourceCodexHome)
$targetFullPath = [System.IO.Path]::GetFullPath($TargetCodexHome)
$useIsolatedHome = $sourceFullPath -ne $targetFullPath

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

    if (Test-Path -LiteralPath $SourcePath) {
        $destDir = Split-Path -Parent $DestinationPath
        if ($destDir) {
            Ensure-Directory -Path $destDir
        }
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force -Recurse
    }
}

if (-not (Test-Path -LiteralPath $SourceCodexHome)) {
    throw "Source Codex home not found: $SourceCodexHome"
}

if ($useIsolatedHome) {
    # Keep the old project-local runtime path available as an explicit fallback for
    # restricted sandbox sessions, but avoid forking conversation history by default.
    Ensure-Directory -Path $TargetCodexHome
    Ensure-Directory -Path (Join-Path $TargetCodexHome "log")
    Ensure-Directory -Path (Join-Path $TargetCodexHome "memories")
    Ensure-Directory -Path (Join-Path $TargetCodexHome "tmp")

    $coreFiles = @(
        ".personality_migration",
        "auth.json",
        "config.toml",
        "history.jsonl",
        "models_cache.json",
        "session_index.jsonl",
        "version.json"
    )

    foreach ($name in $coreFiles) {
        Copy-IfExists `
            -SourcePath (Join-Path $SourceCodexHome $name) `
            -DestinationPath (Join-Path $TargetCodexHome $name)
    }

    Copy-IfExists `
        -SourcePath (Join-Path $SourceCodexHome "skills") `
        -DestinationPath (Join-Path $TargetCodexHome "skills")

    $sessionsSource = Join-Path $SourceCodexHome "sessions"
    $sessionsTarget = Join-Path $TargetCodexHome "sessions"

    if ($CopyAllSessions) {
        Copy-IfExists -SourcePath $sessionsSource -DestinationPath $sessionsTarget
    } else {
        $matches = @(
            Get-ChildItem -Path $sessionsSource -Recurse -Filter "*$SessionId*.jsonl" -ErrorAction SilentlyContinue
        )

        foreach ($match in $matches) {
            $relativePath = $match.FullName.Substring($sessionsSource.Length).TrimStart("\")
            $destination = Join-Path $sessionsTarget $relativePath
            Copy-IfExists -SourcePath $match.FullName -DestinationPath $destination
        }
    }
}

$env:CODEX_HOME = $TargetCodexHome

Write-Host "Using CODEX_HOME: $TargetCodexHome"
Write-Host "Working directory: $WorkingDirectory"
Write-Host "Session id: $SessionId"
Write-Host ("Mode: " + ($(if ($useIsolatedHome) { "isolated-runtime" } else { "shared-main-home" })))

if ($SkipLaunch) {
    Write-Host "SkipLaunch is set. Sync completed without starting Codex."
    exit 0
}

& codex resume $SessionId -C $WorkingDirectory @CodexArgs
