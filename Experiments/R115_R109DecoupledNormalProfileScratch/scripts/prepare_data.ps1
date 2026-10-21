$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & "C:\Users\Rio\anaconda3\python.exe" .\data\prepare_dataset.py
    if ($LASTEXITCODE -ne 0) { throw "R115 data preparation failed" }
}
finally { Pop-Location }
