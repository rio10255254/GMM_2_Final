$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& python (Join-Path $root 'training\train.py') --mode smoke --run-id ('r117_smoke_' + (Get-Date -Format 'yyyyMMdd_HHmmss')) --batch-size-scenes 4 --workers 0 --data-limit 12 --smoke-steps 2
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
