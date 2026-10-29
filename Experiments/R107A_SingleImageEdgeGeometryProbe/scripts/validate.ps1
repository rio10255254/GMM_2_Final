param([string]$Checkpoint = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = python
$arguments = @((Join-Path $root 'validation\validate_prepared.py'))
if ($Checkpoint) { $arguments += @('--checkpoint', $Checkpoint) }
& $python @arguments
exit $LASTEXITCODE

