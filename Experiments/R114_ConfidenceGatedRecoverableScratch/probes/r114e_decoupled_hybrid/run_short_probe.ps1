param(
    [string]$RunId = "r114e_selector_short_probe",
    [int]$Epochs = 6,
    [int]$BatchSize = 8,
    [int]$Workers = 4,
    [int]$Limit = 2048,
    [string]$Device = "cuda"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonExe = "C:\Users\Rio\anaconda3\python.exe"

Push-Location $projectRoot
try {
    & $pythonExe -m probes.r114e_decoupled_hybrid.trainer `
        --run-id $RunId `
        --device $Device `
        --epochs $Epochs `
        --batch-size $BatchSize `
        --workers $Workers `
        --limit $Limit
    if ($LASTEXITCODE -ne 0) {
        throw "R114E short probe failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

