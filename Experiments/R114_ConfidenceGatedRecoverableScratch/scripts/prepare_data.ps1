$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
& python "$Root\scripts\prepare_data.py" --mode materialize
exit $LASTEXITCODE
