param(
    [Parameter(Mandatory = $true)]
    [string]$CodexHome,

    [string]$CodexCommand = "",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RawArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-CodexCommandPath {
    param([string]$PreferredPath)

    if (-not [string]::IsNullOrWhiteSpace($PreferredPath)) {
        return $PreferredPath
    }

    try {
        $resolved = Get-Command codex.cmd -ErrorAction Stop
        return $resolved.Source
    } catch {
        $fallback = Join-Path $env:APPDATA "npm\\codex.cmd"
        if (Test-Path -LiteralPath $fallback) {
            return $fallback
        }
    }

    throw "codex.cmd not found. Install Codex CLI first."
}

function Invoke-CodexNative {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandPath,

        [string[]]$Arguments = @()
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $hasNativePreference = Test-Path Variable:PSNativeCommandUseErrorActionPreference
    if ($hasNativePreference) {
        $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    }

    try {
        $ErrorActionPreference = "Continue"
        if ($hasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $false
        }

        & $CommandPath @Arguments
        $exitCode = $LASTEXITCODE
    } finally {
        if ($hasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativePreference
        }
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw ("Codex command failed with exit code {0}." -f $exitCode)
    }
}

$CodexCommand = Resolve-CodexCommandPath -PreferredPath $CodexCommand
$invokeHome = [System.IO.Path]::GetFullPath($CodexHome)
if (-not (Test-Path -LiteralPath $invokeHome)) {
    throw "Codex home not found: $invokeHome"
}

$resumeAllHelper = Join-Path $PSScriptRoot "codex_resume_all.ps1"
$argumentList = New-Object string[] 0
if ($null -ne $RawArgs) {
    $argumentList = [string[]]$RawArgs
}
$hadPreviousHome = Test-Path Env:CODEX_HOME
$previousHome = if ($hadPreviousHome) { $env:CODEX_HOME } else { $null }

try {
    $env:CODEX_HOME = $invokeHome

    if (
        $argumentList.Length -ge 2 -and
        $argumentList[0] -eq "resume" -and
        ($argumentList -contains "--all") -and
        (Test-Path -LiteralPath $resumeAllHelper)
    ) {
        & $resumeAllHelper -CodexCommand $CodexCommand -CodexHome $invokeHome -RawArgs $argumentList
        return
    }

    Invoke-CodexNative -CommandPath $CodexCommand -Arguments $argumentList
} finally {
    if ($hadPreviousHome) {
        $env:CODEX_HOME = $previousHome
    } else {
        Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
    }
}
