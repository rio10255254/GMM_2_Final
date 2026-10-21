param(
    [ValidateSet('', 'show-recipe', 'dry-run')]
    [Alias('Action')]
    [string]$FormalTrainAction = '',
    [Alias('ProgressRoot')]
    [string]$FormalTrainProgressRoot,
    [Alias('Device')]
    [string]$FormalTrainDevice = 'cuda:0'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$FormalTrainScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FormalTrainRecipePath = Join-Path $FormalTrainScriptRoot 'formal_r26_recipe.json'
$FormalTrainAdapterPath = Join-Path $FormalTrainScriptRoot 'Model\GeoEdge_R26_FormalTrainAdapter.py'

function Get-FormalR26Recipe {
    if (-not (Test-Path -LiteralPath $FormalTrainRecipePath)) {
        throw "找不到正式 R26 recipe：$FormalTrainRecipePath"
    }
    return (Get-Content -LiteralPath $FormalTrainRecipePath -Raw | ConvertFrom-Json)
}

function Resolve-FormalR26Path([string]$RelativePath) {
    return (Join-Path $FormalTrainScriptRoot $RelativePath)
}

function Get-FormalR26PresetStatus {
    $recipe = Get-FormalR26Recipe
    $deployPath = Resolve-FormalR26Path $recipe.deploy_checkpoint_relative
    $seedPath = Resolve-FormalR26Path $recipe.seed_checkpoint_relative
    $psfPath = Resolve-FormalR26Path $recipe.formal_psf_relative
    [pscustomobject]@{
        winner_name = [string]$recipe.winner_name
        winner_tag = [string]$recipe.winner_tag
        recipe_path = $FormalTrainRecipePath
        deploy_checkpoint = $deployPath
        deploy_checkpoint_exists = (Test-Path -LiteralPath $deployPath)
        seed_checkpoint = $seedPath
        seed_checkpoint_exists = (Test-Path -LiteralPath $seedPath)
        formal_psf = $psfPath
        formal_psf_exists = (Test-Path -LiteralPath $psfPath)
        train_source_root = Resolve-FormalR26Path $recipe.train_source_root_relative
        train_label_root = Resolve-FormalR26Path $recipe.train_label_root_relative
        deterministic = [bool]$recipe.deterministic
        seed = [int]$recipe.seed
    }
}

function Show-FormalR26RecipeSummary {
    param(
        [string]$ProgressRoot,
        [string]$Device
    )

    $recipe = Get-FormalR26Recipe
    $lines = @(
        '',
        '=== 正式 R26 recipe 摘要 ===',
        ('- winner: {0}' -f $recipe.winner_name),
        ('- kind: {0}' -f $recipe.kind),
        ('- model_name: {0}' -f $recipe.model_name),
        ('- seed: {0}' -f $recipe.seed),
        ('- deterministic: {0}' -f $recipe.deterministic),
        ('- deploy_checkpoint: {0}' -f (Resolve-FormalR26Path $recipe.deploy_checkpoint_relative)),
        ('- seed_checkpoint: {0}' -f (Resolve-FormalR26Path $recipe.seed_checkpoint_relative)),
        ('- formal_psf: {0}' -f (Resolve-FormalR26Path $recipe.formal_psf_relative)),
        ('- train_source_root: {0}' -f (Resolve-FormalR26Path $recipe.train_source_root_relative)),
        ('- train_label_root: {0}' -f (Resolve-FormalR26Path $recipe.train_label_root_relative)),
        ('- selected_stages: {0}' -f (($recipe.train_include_subdirs | ForEach-Object { [string]$_ }) -join ', ')),
        ('- progress_root: {0}' -f $ProgressRoot),
        ('- device: {0}' -f $Device)
    )
    $lines | ForEach-Object { Write-Host $_ }
}

function Get-FormalR26TrainNativeArgs {
    param(
        [string]$ProgressRoot,
        [string]$Device,
        [switch]$DryRun
    )

    $args = @(
        $FormalTrainAdapterPath,
        '--recipe', $FormalTrainRecipePath,
        '--progress-root', $ProgressRoot
    )
    if (-not [string]::IsNullOrWhiteSpace($Device)) {
        $args += @('--device', $Device)
    }
    if ($DryRun) {
        $args += '--dry-run'
    }
    return ,$args
}

function Get-FormalR26TrainDockerCommand {
    param(
        [string]$Device,
        [switch]$DryRun
    )

    $cmd = @(
        'python /app/Model/GeoEdge_R26_FormalTrainAdapter.py',
        '--recipe /app/formal_r26_recipe.json',
        '--progress-root /app/Traing_Progress'
    )
    if (-not [string]::IsNullOrWhiteSpace($Device)) {
        $cmd += ('--device {0}' -f $Device)
    }
    if ($DryRun) {
        $cmd += '--dry-run'
    }
    return ($cmd -join ' ')
}

if ($FormalTrainAction -eq 'show-recipe') {
    $effectiveProgressRoot = if ([string]::IsNullOrWhiteSpace($FormalTrainProgressRoot)) { '<not set>' } else { $FormalTrainProgressRoot }
    Show-FormalR26RecipeSummary -ProgressRoot $effectiveProgressRoot -Device $FormalTrainDevice
}
elseif ($FormalTrainAction -eq 'dry-run') {
    $effectiveProgressRoot = if ([string]::IsNullOrWhiteSpace($FormalTrainProgressRoot)) {
        Join-Path $FormalTrainScriptRoot '..\輸出結果\訓練結果'
    }
    else {
        $FormalTrainProgressRoot
    }
    $dryRunArgs = Get-FormalR26TrainNativeArgs -ProgressRoot $effectiveProgressRoot -Device $FormalTrainDevice -DryRun
    $payload = [pscustomobject]@{
        recipe_path = $FormalTrainRecipePath
        adapter_path = $FormalTrainAdapterPath
        native_args = $dryRunArgs
        docker_command = (Get-FormalR26TrainDockerCommand -Device $FormalTrainDevice -DryRun)
    }
    $payload | ConvertTo-Json -Depth 6
}
