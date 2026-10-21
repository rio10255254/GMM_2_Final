param(
    [int]$RefreshSeconds = 5,
    [switch]$Once
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = 'C:\Users\Rio\anaconda3\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }
$arguments = @((Join-Path $PSScriptRoot 'monitor_training.py'), '--root', $root, '--refresh', $RefreshSeconds)
if ($Once) { $arguments += '--once' }
& $python @arguments
exit $LASTEXITCODE
