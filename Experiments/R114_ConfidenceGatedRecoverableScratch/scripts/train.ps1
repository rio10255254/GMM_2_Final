param(
    [ValidateSet('controller_probe','geometry_probe','detail_probe_geometry_only','detail_probe_recoverable','formal')]
    [string]$Campaign = 'controller_probe',
    [string]$RunId = '',
    [ValidateSet(12,16)][int]$BatchSize = 16,
    [int]$Workers = 6,
    [int]$ValidationLimit = 128
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = python
$Arguments = @(
    "$Root\training\train.py",
    '--campaign', $Campaign,
    '--batch-size', $BatchSize,
    '--workers', $Workers,
    '--validation-limit', $ValidationLimit
)
if ($RunId) { $Arguments += @('--run-id', $RunId) }
& $Python @Arguments
exit $LASTEXITCODE
