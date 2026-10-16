param(
    [int]$WaitForPid = 80480,
    [string]$Device = 'cuda:0'
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Current = Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue
if ($null -ne $Current) {
    Write-Output "[R63_WAIT] waiting for active confirm runner pid=$WaitForPid"
    Wait-Process -Id $WaitForPid
}
Write-Output '[R63_NEXT] smoke-checking newly added output-module conditions'
& (Join-Path $ScriptRoot 'run_r63_suite.ps1') -Stage smoke -Device $Device
if ($LASTEXITCODE -ne 0) {
    throw 'R63 output-module smoke suite failed'
}
Write-Output '[R63_NEXT] running missing 40-epoch output-module confirmations'
& (Join-Path $ScriptRoot 'run_r63_suite.ps1') -Stage confirm -Device $Device
if ($LASTEXITCODE -ne 0) {
    throw 'R63 output-module confirmation suite failed'
}
Write-Output '[R63_OUTPUT_MODULE_CONFIRM_COMPLETE]'
