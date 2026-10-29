# >>> portable-agent-env >>>
function codex {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

    $codexCmd = $null
    try {
        $resolved = Get-Command codex.cmd -ErrorAction Stop
        $codexCmd = $resolved.Source
    } catch {
        $fallback = Join-Path $env:APPDATA 'npm\codex.cmd'
        if (Test-Path -LiteralPath $fallback) {
            $codexCmd = $fallback
        }
    }

    if ([string]::IsNullOrWhiteSpace($codexCmd)) {
        throw 'codex.cmd not found. Install Codex CLI first.'
    }

    $resumeAllHelper = (Join-Path $ProjectRoot '_portable_env_sim_20260318\install\scripts\codex_resume_all.ps1')

    if (
        $Args.Count -ge 2 -and
        $Args[0] -eq 'resume' -and
        ($Args -contains '--all') -and
        (Test-Path -LiteralPath $resumeAllHelper)
    ) {
        & $resumeAllHelper -CodexCommand $codexCmd -RawArgs $Args
        return
    }

    & $codexCmd @Args
}
# <<< portable-agent-env <<<

