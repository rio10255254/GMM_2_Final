param(
    [string]$Device = "cuda:0",
    [int]$Seed = 750031,
    [int]$Epochs = 100,
    [switch]$PrepareOnly
)

$ErrorActionPreference = "Stop"
$Python = python
$Experiment = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot "launch_r75.py"
$DatasetBuilder = Join-Path $PSScriptRoot "r75_dataset.py"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

& $Python $DatasetBuilder --profile formal
if ($LASTEXITCODE -ne 0) { throw "R75 formal dataset preparation failed." }

& $Python $Launcher --profile formal --dry-run --device $Device --seed $Seed --num-epoch $Epochs
if ($LASTEXITCODE -ne 0) { throw "R75 pre-training audit failed." }

if ($PrepareOnly) {
    Write-Host "R75 formal data and all pre-training checks are ready. Training was not started."
    exit 0
}

& $Python $Launcher --profile formal --device $Device --seed $Seed --num-epoch $Epochs
if ($LASTEXITCODE -ne 0) { throw "R75 formal training failed." }
