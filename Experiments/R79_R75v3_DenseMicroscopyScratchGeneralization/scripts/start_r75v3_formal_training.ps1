param(
    [string]$Device = "cuda:0",
    [int]$Seed = 752031,
    [int]$Epochs = 100,
    [switch]$PrepareOnly
)

$ErrorActionPreference = "Stop"
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Launcher = Join-Path $PSScriptRoot "launch_r75v3.py"
$DatasetBuilder = Join-Path $PSScriptRoot "r75v3_dataset.py"
$Experiment = Split-Path -Parent $PSScriptRoot
$LiveValidationBuilder = Join-Path $Experiment "tools\prepare_live_validation.py"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

& $Python $LiveValidationBuilder
if ($LASTEXITCODE -ne 0) { throw "R75-v3 live-validation preparation failed." }

& $Python $DatasetBuilder --profile formal
if ($LASTEXITCODE -ne 0) { throw "R75-v3 formal dataset preparation failed." }

& $Python $Launcher --profile formal --dry-run --device $Device --seed $Seed --num-epoch $Epochs --no-amp
if ($LASTEXITCODE -ne 0) { throw "R75-v3 pre-training audit failed." }

if ($PrepareOnly) {
    Write-Host "R75-v3 formal data and all pre-training checks are ready. Training was not started."
    exit 0
}

& $Python $Launcher --profile formal --device $Device --seed $Seed --num-epoch $Epochs --no-amp --run-suffix "dense_multiscale_e${Epochs}"
if ($LASTEXITCODE -ne 0) { throw "R75-v3 formal training failed." }
