param(
    [ValidateSet('reliability_probe','split_profile_probe','formal')]
    [string]$Campaign = 'split_profile_probe',
    [string]$RunId = '',
    [ValidateSet(12)][int]$BatchSize = 12,
    [int]$Workers = 4,
    [int]$ValidationLimit = 0,
    [ValidateRange(1,12)][int]$MicrobatchSize = 6,
    [switch]$Smoke,
    [switch]$FullModelSmoke,
    [switch]$ForceFp32,
    [switch]$AuthorizeFormal
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = python
$Trainer = Join-Path $Root 'training\train_split_profile.py'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python runtime not found: $Python"
}
if (-not (Test-Path -LiteralPath $Trainer -PathType Leaf)) {
    throw "Split-profile trainer not found: $Trainer"
}
if ($Campaign -eq 'formal' -and -not $AuthorizeFormal) {
    throw 'Formal training requires -AuthorizeFormal.'
}
if ($AuthorizeFormal -and $Campaign -ne 'formal') {
    throw '-AuthorizeFormal may only be used with -Campaign formal.'
}

$Arguments = @(
    $Trainer,
    '--campaign', $Campaign,
    '--batch-size', $BatchSize,
    '--workers', $Workers,
    '--validation-limit', $ValidationLimit,
    '--microbatch-size', $MicrobatchSize
)
if ($RunId) { $Arguments += @('--run-id', $RunId) }
if ($Smoke) { $Arguments += '--smoke' }
if ($FullModelSmoke) {
    if (-not $Smoke) { throw '-FullModelSmoke requires -Smoke.' }
    $Arguments += '--full-model-smoke'
}
if ($ForceFp32) { $Arguments += '--force-fp32' }
if ($AuthorizeFormal) { $Arguments += '--authorize-formal' }

& $Python @Arguments
exit $LASTEXITCODE
