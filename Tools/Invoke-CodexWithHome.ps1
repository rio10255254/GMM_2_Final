param(
    [Parameter(Mandatory = $true)]
    [string]$CodexHome,

    [string]$CodexCommand = "",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RawArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($CodexCommand)) {
    $resolved = Get-Command codex.cmd -ErrorAction Stop
    $CodexCommand = $resolved.Source
}

$invokeHome = [System.IO.Path]::GetFullPath($CodexHome)
if (-not (Test-Path -LiteralPath $invokeHome)) {
    throw "Codex home not found: $invokeHome"
}

$resumeAllHelper = Join-Path $PSScriptRoot "codex_resume_all.ps1"
$argumentList = @($RawArgs)
$hadPreviousHome = Test-Path Env:CODEX_HOME
$previousHome = if ($hadPreviousHome) { $env:CODEX_HOME } else { $null }

try {
    $env:CODEX_HOME = $invokeHome

    if (
        $argumentList.Count -ge 2 -and
        $argumentList[0] -eq "resume" -and
        ($argumentList -contains "--all") -and
        (Test-Path -LiteralPath $resumeAllHelper)
    ) {
        & $resumeAllHelper -CodexCommand $CodexCommand -CodexHome $invokeHome -RawArgs $argumentList
        return
    }

    & $CodexCommand @argumentList
} finally {
    if ($hadPreviousHome) {
        $env:CODEX_HOME = $previousHome
    } else {
        Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
    }
}
