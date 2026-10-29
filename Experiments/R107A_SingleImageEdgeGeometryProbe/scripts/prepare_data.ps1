param([int]$Limit = 0)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = python
& $python (Join-Path $root 'data\prepare_dataset.py') --limit $Limit
exit $LASTEXITCODE

