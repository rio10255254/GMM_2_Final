$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\Rio\anaconda3\python.exe'
$runId = 'r116_probe_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
& $python (Join-Path $root 'training\train.py') --mode probe --run-id $runId
exit $LASTEXITCODE
