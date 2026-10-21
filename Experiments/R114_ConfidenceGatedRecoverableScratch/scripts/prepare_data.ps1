$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
& 'C:\Users\Rio\anaconda3\python.exe' "$Root\scripts\prepare_data.py" --mode materialize
exit $LASTEXITCODE
