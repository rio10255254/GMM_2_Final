param(
    [string]$RunId = "r114d_selector_short_probe_20260831",
    [int]$Epochs = 6,
    [int]$BatchSize = 8,
    [int]$Workers = 4,
    [int]$Limit = 2048,
    [string]$Device = "cuda"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonExe = python

Push-Location $projectRoot
try {
    & $pythonExe -m probes.r114d_action_selector.trainer `
        --run-id $RunId `
        --device $Device `
        --epochs $Epochs `
        --batch-size $BatchSize `
        --workers $Workers `
        --limit $Limit
    if ($LASTEXITCODE -ne 0) {
        throw "R114D short probe failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
