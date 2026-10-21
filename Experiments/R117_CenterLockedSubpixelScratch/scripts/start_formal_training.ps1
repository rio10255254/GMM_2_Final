$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runId = 'r117_formal_scratch_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
& 'C:\Users\Rio\anaconda3\python.exe' (Join-Path $root 'training\train.py') --mode formal --run-id $runId
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
