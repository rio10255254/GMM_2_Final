param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& 'C:\Users\Rio\anaconda3\python.exe' (Join-Path $root 'data\prepare_dataset.py')
exit $LASTEXITCODE
