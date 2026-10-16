Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-HostSmoke {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HostName,

        [Parameter(Mandatory = $true)]
        [string]$Executable,

        [string[]]$PrefixArgs = @()
    )

    $childScript = @'
$ErrorActionPreference = "Stop"

$commands = @(
    @{ name = "codex"; arguments = @("--version") },
    @{ name = "codex-yunyi"; arguments = @("--version") },
    @{ name = "codex-openai"; arguments = @("--version") }
)

$wrapperPath = Join-Path $env:USERPROFILE ".portable-agent-env\scripts\Invoke-CodexWithHome.ps1"
$homePath = Join-Path $env:USERPROFILE ".codex-yunyi"
$noopPath = Join-Path $env:USERPROFILE ".portable-agent-env\scripts\testdata\noop.cmd"

try {
    $wrapperNoArgsOutput = & $wrapperPath -CodexHome $homePath -CodexCommand $noopPath 2>&1 | Out-String
    $wrapperNoArgsOk = $LASTEXITCODE -eq 0
    $wrapperNoArgsError = ""
} catch {
    $wrapperNoArgsOk = $false
    $wrapperNoArgsError = $_.Exception.Message
}

$results = foreach ($item in $commands) {
    $output = & $item.name @($item.arguments) 2>&1 | Out-String
    [pscustomobject]@{
        command = $item.name
        ok = $LASTEXITCODE -eq 0
        output = $output.Trim()
    }
}

try {
    codex-status *> $null
    $statusOk = $true
    $statusError = ""
} catch {
    $statusOk = $false
    $statusError = $_.Exception.Message
}

[pscustomobject]@{
    codex_command = (Get-Command codex).CommandType.ToString()
    results = $results
    codex_status_ok = $statusOk
    codex_status_error = $statusError
    wrapper_no_args_ok = $wrapperNoArgsOk
    wrapper_no_args_error = $wrapperNoArgsError
} | ConvertTo-Json -Depth 5 -Compress
'@

    $childScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("codex_verify_" + [guid]::NewGuid().ToString() + ".ps1")
    try {
        Set-Content -LiteralPath $childScriptPath -Value $childScript -Encoding UTF8

        $allArgs = @($PrefixArgs + @("-NoLogo", "-File", $childScriptPath))
        $rawOutput = & $Executable @allArgs
        $exitCode = $LASTEXITCODE
        $jsonText = ($rawOutput | Out-String).Trim()
    } finally {
        if (Test-Path -LiteralPath $childScriptPath) {
            Remove-Item -LiteralPath $childScriptPath -Force -ErrorAction SilentlyContinue
        }
    }

    if ($exitCode -ne 0) {
        throw ("{0} failed with exit code {1}: {2}" -f $HostName, $exitCode, $jsonText)
    }

    try {
        $payload = $jsonText | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw ("{0} returned non-JSON output: {1}" -f $HostName, $jsonText)
    }

    foreach ($result in @($payload.results)) {
        if (-not $result.ok) {
            throw ("{0} failed `{1}`: {2}" -f $HostName, $result.command, $result.output)
        }
    }

    if (-not $payload.codex_status_ok) {
        throw ("{0} failed `codex-status`: {1}" -f $HostName, $payload.codex_status_error)
    }

    if (-not $payload.wrapper_no_args_ok) {
        throw ("{0} failed wrapper no-args smoke test: {1}" -f $HostName, $payload.wrapper_no_args_error)
    }

    $resumeArgs = @($PrefixArgs + @("-NoLogo", "-Command", "codex resume --all"))
    $resumeText = ("`n`n" | & $Executable @resumeArgs 2>&1 | Out-String).Trim()
    $resumeExitCode = $LASTEXITCODE
    if ($resumeExitCode -ne 0) {
        throw ("{0} failed `codex resume --all`: {1}" -f $HostName, $resumeText)
    }

    return [pscustomobject]@{
        host = $HostName
        codex_command = $payload.codex_command
        commands = @($payload.results.command) -join ", "
    }
}

$summary = @(
    Invoke-HostSmoke -HostName "pwsh" -Executable "pwsh"
    Invoke-HostSmoke -HostName "powershell" -Executable "powershell" -PrefixArgs @("-ExecutionPolicy", "Bypass")
)

$summary | Format-Table -AutoSize
