param([int]$Steps = 2)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\Rio\anaconda3\python.exe'
& $python (Join-Path $root 'training\train.py') --run-id r107_smoke --epochs 1 --batch-size 2 --workers 0 --smoke-steps $Steps --data-limit 8 --validation-limit 8 --allow-partial-data --no-amp
exit $LASTEXITCODE

