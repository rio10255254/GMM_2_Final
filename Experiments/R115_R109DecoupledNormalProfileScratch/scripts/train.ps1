param(
    [string]$RunId = "r115_formal_scratch_20260831",
    [int]$Workers = 4
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & python .\training\train.py `
        --run-id $RunId --device cuda --batch-size 8 --workers $Workers --authorize-formal
    if ($LASTEXITCODE -ne 0) { throw "R115 formal training failed" }
}
finally { Pop-Location }
