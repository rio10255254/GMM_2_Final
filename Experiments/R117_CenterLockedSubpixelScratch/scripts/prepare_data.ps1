$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& python (Join-Path $root 'data\prepare_dataset.py') --workers 6
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
