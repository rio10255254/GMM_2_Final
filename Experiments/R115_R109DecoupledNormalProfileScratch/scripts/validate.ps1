$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & python -m pytest .\tests -q
    if ($LASTEXITCODE -ne 0) { throw "R115 tests failed" }
    & python .\data\prepare_dataset.py
    if ($LASTEXITCODE -ne 0) { throw "R115 data validation failed" }
    $authorization = Get-Content -LiteralPath .\formal_authorization.json -Raw | ConvertFrom-Json
    Write-Host ("R115 tests and data: PASS | formal authorized: " + $authorization.authorized)
}
finally { Pop-Location }

