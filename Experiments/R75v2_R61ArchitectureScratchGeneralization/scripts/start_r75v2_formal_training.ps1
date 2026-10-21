param(
    [string]$Device = "cuda:0",
    [int]$Seed = 752031,
    [int]$Epochs = 100,
    [switch]$PrepareOnly
)

$ErrorActionPreference = "Stop"
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Launcher = Join-Path $PSScriptRoot "launch_r75v2.py"
$DatasetBuilder = Join-Path $PSScriptRoot "r75v2_dataset.py"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

& $Python $DatasetBuilder --profile formal
if ($LASTEXITCODE -ne 0) { throw "R75-v2 formal dataset preparation failed." }

& $Python $Launcher --profile formal --dry-run --device $Device --seed $Seed --num-epoch $Epochs --no-amp
if ($LASTEXITCODE -ne 0) { throw "R75-v2 pre-training audit failed." }

if ($PrepareOnly) {
    Write-Host "R75-v2 formal data and all pre-training checks are ready. Training was not started."
    exit 0
}

& $Python $Launcher --profile formal --device $Device --seed $Seed --num-epoch $Epochs --no-amp --run-suffix "diverse_data_e100"
if ($LASTEXITCODE -ne 0) { throw "R75-v2 formal training failed." }
