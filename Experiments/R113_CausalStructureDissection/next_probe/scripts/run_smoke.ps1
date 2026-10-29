$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = python

& $Python (Join-Path $PSScriptRoot 'prepare_selection.py')
& $Python -m pytest (Join-Path $Root 'tests') -q
& $Python (Join-Path $PSScriptRoot 'run_probe.py') --mode smoke --arm both
& $Python (Join-Path $PSScriptRoot 'validate_probe.py')

