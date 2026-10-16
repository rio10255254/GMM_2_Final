param(
    [int]$WaitForPid = 75968,
    [string]$Device = 'cuda:0'
)

$ErrorActionPreference = 'Stop'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentRoot = Split-Path -Parent $ScriptRoot
$Current = Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue
if ($null -ne $Current) {
    Write-Output "[R63_WAIT] waiting for 40-epoch suite pid=$WaitForPid"
    Wait-Process -Id $WaitForPid
}

Push-Location $ExperimentRoot
try {
    Write-Output '[R63_VERIFY] requiring all 32 forty-epoch runs'
    & python (Join-Path $ScriptRoot 'collect_training_runs.py') --epochs 40 --require-complete
    if ($LASTEXITCODE -ne 0) { throw 'R63 40-epoch collection failed' }

    & python (Join-Path $ScriptRoot 'audit_convergence_gate.py')
    if ($LASTEXITCODE -ne 0) { throw 'R63 convergence gate audit failed' }
    $Gate = Get-Content (Join-Path $ExperimentRoot 'results\convergence_gate.json') -Raw | ConvertFrom-Json
    if (-not [bool]$Gate.extend_to_epoch60) {
        Write-Output '[R63_EXTENSION_NOT_REQUIRED]'
        exit 0
    }

    Write-Output '[R63_EXTEND] continuing every condition and seed from epoch 40 to epoch 60'
    & (Join-Path $ScriptRoot 'extend_r63_suite.ps1') -SourceEpoch 40 -TargetEpoch 60 -Device $Device
    if ($LASTEXITCODE -ne 0) { throw 'R63 global extension failed' }

    Write-Output '[R63_VERIFY] requiring all 32 sixty-epoch trajectories'
    & python (Join-Path $ScriptRoot 'collect_training_runs.py') --epochs 60 --require-complete
    if ($LASTEXITCODE -ne 0) { throw 'R63 60-epoch collection failed' }
    & python (Join-Path $ScriptRoot 'audit_config_contrasts.py')
    if ($LASTEXITCODE -ne 0) { throw 'R63 config contrast audit failed' }
    & python (Join-Path $ScriptRoot 'audit_checkpoint_structure.py')
    if ($LASTEXITCODE -ne 0) { throw 'R63 checkpoint structure audit failed' }
    & python (Join-Path $ScriptRoot 'audit_parameter_deltas.py')
    if ($LASTEXITCODE -ne 0) { throw 'R63 parameter delta audit failed' }
    Write-Output '[R63_GLOBAL_EXTENSION_COMPLETE]'
}
finally {
    Pop-Location
}
