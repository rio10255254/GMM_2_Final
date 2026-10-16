param([string]$Checkpoint = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\Rio\anaconda3\python.exe'
$arguments = @((Join-Path $root 'validation\validate_prepared.py'))
if ($Checkpoint) { $arguments += @('--checkpoint', $Checkpoint) }
& $python @arguments
exit $LASTEXITCODE

