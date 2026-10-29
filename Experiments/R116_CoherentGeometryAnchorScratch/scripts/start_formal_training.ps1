$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = python
$runId = 'r116_formal_scratch_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
& $python (Join-Path $root 'training\train.py') --mode formal --run-id $runId
exit $LASTEXITCODE
