param(
    [string]$RunId = '',
    [int]$Epochs = 60,
    [int]$BatchSize = 8,
    [int]$Workers = 4
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = python
$arguments = @((Join-Path $root 'training\train.py'), '--epochs', $Epochs, '--batch-size', $BatchSize, '--workers', $Workers)
if ($RunId) { $arguments += @('--run-id', $RunId) }
& $python @arguments
exit $LASTEXITCODE

