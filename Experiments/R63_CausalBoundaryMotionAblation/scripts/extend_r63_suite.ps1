param(
    [int]$SourceEpoch = 40,
    [int]$TargetEpoch = 60,
    [string]$Device = 'cuda:0'
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUNBUFFERED = '1'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentRoot = Split-Path -Parent $ScriptRoot
$Launcher = Join-Path $ScriptRoot 'launch_r63.py'
$RunRoot = Join-Path $ExperimentRoot 'results\training_runs'
$ExclusionPath = Join-Path $ExperimentRoot 'results\excluded_training_runs.json'
$ExcludedNames = @()
if (Test-Path -LiteralPath $ExclusionPath) {
    $ExcludedNames = @((Get-Content -LiteralPath $ExclusionPath -Raw | ConvertFrom-Json).excluded_run_names)
}
$Variants = @(
    'full_control',
    'no_geometry_anchor',
    'no_motion_consistency',
    'no_geometry_no_motion',
    'no_shape_geometry',
    'no_global_boundary_position',
    'no_identity_boundary_guard',
    'no_region_boundary_teacher',
    'no_sequence_consistency',
    'no_known_shift_motion',
    'no_shift_equivariance',
    'no_boundary_residual_adapter',
    'no_raw_position_anchor',
    'no_quality_gate',
    'shift_safe_matched',
    'standard_upsample_matched'
)
$Seeds = @(1261200, 1261217)

foreach ($Seed in $Seeds) {
    foreach ($Variant in $Variants) {
        $Pattern = "training_progress_R63_MOSR_${Variant}_s${Seed}_*"
        $CompletedTarget = Get-ChildItem -LiteralPath $RunRoot -Directory -Filter $Pattern -ErrorAction SilentlyContinue |
            Where-Object {
                ($ExcludedNames -notcontains $_.Name) -and
                (Test-Path -LiteralPath (Join-Path $_.FullName ("epoch_{0:D3}.pth.tar" -f $TargetEpoch)))
            } |
            Select-Object -First 1
        if ($null -ne $CompletedTarget) {
            Write-Output "[R63_SKIP_EXTENDED] seed=$Seed variant=$Variant"
            continue
        }
        $SourceRun = Get-ChildItem -LiteralPath $RunRoot -Directory -Filter $Pattern -ErrorAction SilentlyContinue |
            Where-Object {
                ($ExcludedNames -notcontains $_.Name) -and
                (Test-Path -LiteralPath (Join-Path $_.FullName ("epoch_{0:D3}.pth.tar" -f $SourceEpoch)))
            } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -eq $SourceRun) {
            throw "Missing source run: seed=$Seed variant=$Variant epoch=$SourceEpoch"
        }
        $Resume = Join-Path $SourceRun.FullName ("epoch_{0:D3}.pth.tar" -f $SourceEpoch)
        & python $Launcher `
            --variant $Variant `
            --seed $Seed `
            --epochs $TargetEpoch `
            --max-train-batches 32 `
            --val-every 4 `
            --seq-val-pairs 256 `
            --checkpoint-every 4 `
            --resume-checkpoint $Resume `
            --continue-training `
            --device $Device
        if ($LASTEXITCODE -ne 0) {
            throw "R63 extension failed: seed=$Seed variant=$Variant"
        }
    }
}
