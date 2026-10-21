$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = 'C:\Users\Rio\anaconda3\python.exe'

& $Python (Join-Path $PSScriptRoot 'prepare_selection.py')
& $Python -m pytest (Join-Path $Root 'tests') -q
& $Python (Join-Path $PSScriptRoot 'run_probe.py') --mode smoke --arm both
& $Python (Join-Path $PSScriptRoot 'validate_probe.py')

