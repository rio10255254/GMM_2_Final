param(
    [string]$MatlabExe = 'C:\Program Files\MATLAB\R2025b\bin\matlab.exe',
    [int[]]$SubsetIndices = @(1..100),
    [string]$OutputRoot = '',
    [switch]$ForceCpu
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptsDir = Join-Path $scriptDir 'scripts'
$scriptDirMatlab = ($scriptDir -replace '\\', '/')
$scriptsDirMatlab = ($scriptsDir -replace '\\', '/')

if (-not (Test-Path $MatlabExe)) {
    throw "MATLAB not found: $MatlabExe"
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $scriptDir 'outputs\reasonable_v1_full100'
}

$outputRootMatlab = ($OutputRoot -replace '\\', '/')
$subsetLiteral = '[' + (($SubsetIndices | ForEach-Object { $_.ToString() }) -join ' ') + ']'
$useGpuLiteral = if ($ForceCpu) { 'false' } else { '[]' }

$matlabCommand = @"
addpath('$scriptsDirMatlab');
summary = HDR_fitting_2D_WholeFOV_reasonable_v1( ...
    'subset_indices', $subsetLiteral, ...
    'output_root', '$outputRootMatlab', ...
    'use_gpu', $useGpuLiteral);
disp(summary);
"@

& $MatlabExe -batch $matlabCommand
