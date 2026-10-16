$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = 'C:\Users\Rio\anaconda3\python.exe'

& $Python -m pytest (Join-Path $Root 'tests') -q
& $Python (Join-Path $PSScriptRoot 'check_supervision_capability.py')
& $Python (Join-Path $PSScriptRoot 'run_probe.py') --mode smoke --arm bounded_detail_supervised
& $Python (Join-Path $PSScriptRoot 'validate_supervised_smoke.py')
