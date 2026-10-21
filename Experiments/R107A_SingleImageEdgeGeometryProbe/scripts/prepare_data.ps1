param([int]$Limit = 0)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\Rio\anaconda3\python.exe'
& $python (Join-Path $root 'data\prepare_dataset.py') --limit $Limit
exit $LASTEXITCODE

