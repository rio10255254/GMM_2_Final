param(
    [string]$RunId = "r115_data_architecture_ablation_20260831",
    [string]$Device = "cuda"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & "C:\Users\Rio\anaconda3\python.exe" .\probes\run_ablation_probe.py --run-id $RunId --device $Device
    if ($LASTEXITCODE -ne 0) { throw "R115 ablation probe failed" }
}
finally { Pop-Location }

