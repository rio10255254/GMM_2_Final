param(
    [string]$MatlabExe = 'C:\Program Files\MATLAB\R2025b\bin\matlab.exe',
    [string]$ProfileName = 'subset4',
    [int[]]$SubsetIndices = @(1, 56, 60, 100),
    [string[]]$ExperimentNames = @(),
    [switch]$SkipOptionalExperiment,
    [switch]$ForceCpu,
    [switch]$AggregateOnly
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptsDir = Join-Path $scriptDir 'scripts'
$scriptDirMatlab = ($scriptDir -replace '\\', '/')
$scriptsDirMatlab = ($scriptsDir -replace '\\', '/')

if (-not (Test-Path $MatlabExe)) {
    throw "MATLAB not found: $MatlabExe"
}

$subsetLiteral = '[' + (($SubsetIndices | ForEach-Object { $_.ToString() }) -join ' ') + ']'
$includeOptionalLiteral = if ($SkipOptionalExperiment) { 'false' } else { 'true' }
$useGpuLiteral = if ($ForceCpu) { 'false' } else { '[]' }

$experimentLiteral = "strings(0,1)"
if ($ExperimentNames.Count -gt 0) {
    $quotedNames = $ExperimentNames | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }
    $experimentLiteral = "string({" + ($quotedNames -join ',') + "})"
}

$matlabCommand = if ($AggregateOnly) {
@"
addpath('$scriptsDirMatlab');
summary = vlab_aggregate_existing_results('$scriptDirMatlab', 'experiment_names', $experimentLiteral);
disp(summary);
"@
} else {
@"
addpath('$scriptsDirMatlab');
summary = vlab_run_validation_lab( ...
    'profile_name', '$ProfileName', ...
    'subset_indices', $subsetLiteral, ...
    'include_optional_experiment', $includeOptionalLiteral, ...
    'experiment_names', $experimentLiteral, ...
    'use_gpu', $useGpuLiteral);
disp(summary);
"@
}

& $MatlabExe -batch $matlabCommand
