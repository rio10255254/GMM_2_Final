param(
    [ValidateSet('smoke','screen','confirm')]
    [string]$Stage = 'smoke',
    [string]$Device = 'cuda:0'
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUNBUFFERED = '1'
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentRoot = Split-Path -Parent $ScriptRoot
$RunRoot = Join-Path $ExperimentRoot 'results\training_runs'
$ExclusionPath = Join-Path $ExperimentRoot 'results\excluded_training_runs.json'
$ExcludedNames = @()
if (Test-Path -LiteralPath $ExclusionPath) {
    $ExcludedNames = @((Get-Content -LiteralPath $ExclusionPath -Raw | ConvertFrom-Json).excluded_run_names)
}
$Launcher = Join-Path $ScriptRoot 'launch_r63.py'
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

if ($Stage -eq 'smoke') {
    $Seeds = @(1261200)
    $Epochs = 1
    $Batches = 2
    $ValEvery = 1
    $SeqValPairs = 8
}
elseif ($Stage -eq 'screen') {
    $Seeds = @(1261200)
    $Epochs = 40
    $Batches = 32
    $ValEvery = 4
    $SeqValPairs = 256
}
else {
    $Seeds = @(1261200, 1261217)
    $Epochs = 40
    $Batches = 32
    $ValEvery = 4
    $SeqValPairs = 256
}

foreach ($Seed in $Seeds) {
    foreach ($Variant in $Variants) {
        $Pattern = "training_progress_R63_MOSR_${Variant}_s${Seed}_*"
        $Completed = Get-ChildItem -LiteralPath $RunRoot -Directory -Filter $Pattern -ErrorAction SilentlyContinue |
            Where-Object {
                ($ExcludedNames -notcontains $_.Name) -and
                (Test-Path -LiteralPath (Join-Path $_.FullName ("epoch_{0:D3}.pth.tar" -f $Epochs)))
            } |
            Select-Object -First 1
        if ($null -ne $Completed) {
            Write-Output "[R63_SKIP_COMPLETE] seed=$Seed variant=$Variant run=$($Completed.FullName)"
            continue
        }
        & python $Launcher `
            --variant $Variant `
            --seed $Seed `
            --epochs $Epochs `
            --max-train-batches $Batches `
            --val-every $ValEvery `
            --seq-val-pairs $SeqValPairs `
            --device $Device
        if ($LASTEXITCODE -ne 0) {
            throw "R63 failed: stage=$Stage seed=$Seed variant=$Variant"
        }
    }
}
