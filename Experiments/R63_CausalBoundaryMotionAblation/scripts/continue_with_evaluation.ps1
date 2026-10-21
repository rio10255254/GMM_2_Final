param(
    [int]$WaitForPid = 79308,
    [string]$Device = 'cuda:0'
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentRoot = Split-Path -Parent $ScriptRoot
$Current = Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue
if ($null -ne $Current) {
    Write-Output "[R63_WAIT] waiting for extension/audit runner pid=$WaitForPid"
    Wait-Process -Id $WaitForPid
}

Push-Location $ExperimentRoot
try {
    $GatePath = Join-Path $ExperimentRoot 'results\convergence_gate.json'
    if (-not (Test-Path -LiteralPath $GatePath)) { throw 'Missing convergence gate result' }
    $Gate = Get-Content $GatePath -Raw | ConvertFrom-Json
    $Budget = if ([bool]$Gate.extend_to_epoch60) { 60 } else { 40 }
    & python (Join-Path $ScriptRoot 'collect_training_runs.py') --epochs $Budget --require-complete
    if ($LASTEXITCODE -ne 0) { throw 'R63 final training collection failed' }

    Write-Output '[R63_EVAL] reconstructing every frozen evaluation population'
    & python (Join-Path $ScriptRoot 'run_reconstruction_suite.py') --device $Device
    if ($LASTEXITCODE -ne 0) { throw 'R63 reconstruction suite failed' }

    Write-Output '[R63_EVAL] running locked static, displacement, and known-shift metrics'
    & python (Join-Path $ScriptRoot 'run_metric_suite.py')
    if ($LASTEXITCODE -ne 0) { throw 'R63 metric suite failed' }
    & python (Join-Path $ScriptRoot 'aggregate_r63_results.py') --bootstrap 4000
    if ($LASTEXITCODE -ne 0) { throw 'R63 aggregate failed' }
    & python (Join-Path $ScriptRoot 'audit_claim_support.py')
    if ($LASTEXITCODE -ne 0) { throw 'R63 claim audit failed' }
    & python (Join-Path $ScriptRoot 'audit_full_vs_raw.py')
    if ($LASTEXITCODE -ne 0) { throw 'R63 full-versus-Raw audit failed' }

    Write-Output '[R63_EVAL] running inference-only output-protection audit'
    & python (Join-Path $ScriptRoot 'run_output_protection_suite.py') --device $Device
    if ($LASTEXITCODE -ne 0) { throw 'R63 output-protection suite failed' }
    & python (Join-Path $ScriptRoot 'aggregate_output_protection.py') --bootstrap 4000
    if ($LASTEXITCODE -ne 0) { throw 'R63 output-protection aggregation failed' }

    $MatlabScriptRoot = $ScriptRoot.Replace('\', '/')
    & matlab -batch "addpath('$MatlabScriptRoot'); build_r63_figures; build_r63_visual_examples;"
    if ($LASTEXITCODE -ne 0) { throw 'R63 MATLAB figure generation failed' }
    Write-Output '[R63_EVALUATION_COMPLETE]'
}
finally {
    Pop-Location
}
