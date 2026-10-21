param([string]$RunId = "r115_contract_smoke")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & "C:\Users\Rio\anaconda3\python.exe" .\training\train.py `
        --run-id $RunId --device cuda --batch-size 2 --workers 0 --data-limit 8 --smoke-steps 2
    if ($LASTEXITCODE -ne 0) { throw "R115 smoke failed" }
}
finally { Pop-Location }

