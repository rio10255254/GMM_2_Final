$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Matlab = "C:\Program Files\MATLAB\R2025b\bin\matlab.exe"

Write-Host "R100 design validation: core experiments" -ForegroundColor Cyan
& $Python (Join-Path $Root "analysis\run_core_validation.py")
if ($LASTEXITCODE -ne 0) { throw "Core validation failed" }

Write-Host "R100 design validation: ACM photometric audit" -ForegroundColor Cyan
& $Matlab -batch "run('$((Join-Path $Root 'analysis\run_acm_photometric_audit.m').Replace("'", "''"))')"
if ($LASTEXITCODE -ne 0) { throw "ACM audit failed" }

Write-Host "R100 design validation: integration and checks" -ForegroundColor Cyan
& $Python (Join-Path $Root "analysis\summarize_validation.py")
if ($LASTEXITCODE -ne 0) { throw "Validation integration failed" }
& $Python -m pytest (Join-Path $Root "tests") -q
if ($LASTEXITCODE -ne 0) { throw "Validation checks failed" }

Write-Host "R100 design validation complete" -ForegroundColor Green

