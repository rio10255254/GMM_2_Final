param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& python (Join-Path $root 'data\prepare_dataset.py')
exit $LASTEXITCODE
