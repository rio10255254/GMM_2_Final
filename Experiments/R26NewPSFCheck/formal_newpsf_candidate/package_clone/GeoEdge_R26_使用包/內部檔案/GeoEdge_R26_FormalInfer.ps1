param(
    [ValidateSet('', 'show-recipe', 'dry-run-demo', 'dry-run-custom')]
    [Alias('Action')]
    [string]$FormalInferAction = '',
    [Alias('InputDir')]
    [string]$FormalInferInputDir,
    [Alias('ReconRoot')]
    [string]$FormalInferReconRoot,
    [Alias('Device')]
    [string]$FormalInferDevice = 'cuda:0'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$FormalInferScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FormalInferRecipePath = Join-Path $FormalInferScriptRoot 'formal_r26_recipe.json'
$FormalInferScriptPath = Join-Path $FormalInferScriptRoot 'Model\GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py'

function Get-FormalR26InferRecipe {
    if (-not (Test-Path -LiteralPath $FormalInferRecipePath)) {
        throw "找不到正式 R26 recipe：$FormalInferRecipePath"
    }
    return (Get-Content -LiteralPath $FormalInferRecipePath -Raw | ConvertFrom-Json)
}

function Resolve-FormalInferPath([string]$RelativePath) {
    return (Join-Path $FormalInferScriptRoot $RelativePath)
}

function Get-FormalR26InferNativeArgs {
    param(
        [string]$InputDir,
        [string]$ReconRoot,
        [string]$Device
    )

    $recipe = Get-FormalR26InferRecipe
    $weights = Resolve-FormalInferPath $recipe.deploy_checkpoint_relative
    $args = @(
        $FormalInferScriptPath,
        '--weights', $weights,
        '--input-dir', $InputDir,
        '--recon-root', $ReconRoot,
        '--psf-from-ckpt'
    )
    if (-not [string]::IsNullOrWhiteSpace($Device)) {
        $args += @('--device', $Device)
    }
    return ,$args
}

function Get-FormalR26InferDockerCommand {
    param(
        [string]$InputDir,
        [string]$ReconRoot,
        [string]$Device
    )

    $cmd = @(
        'python /app/Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py',
        '--weights /app/weights/r26_sm035_best_tradeoff.pth.tar',
        ('--input-dir {0}' -f $InputDir),
        ('--recon-root {0}' -f $ReconRoot),
        '--psf-from-ckpt'
    )
    if (-not [string]::IsNullOrWhiteSpace($Device)) {
        $cmd += ('--device {0}' -f $Device)
    }
    return ($cmd -join ' ')
}

function Show-FormalR26InferSummary {
    param(
        [string]$InputDir,
        [string]$ReconRoot,
        [string]$Device
    )
    $recipe = Get-FormalR26InferRecipe
    $lines = @(
        '',
        '=== 正式 R26 inference 摘要 ===',
        ('- winner: {0}' -f $recipe.winner_name),
        ('- weights: {0}' -f (Resolve-FormalInferPath $recipe.deploy_checkpoint_relative)),
        ('- input: {0}' -f $InputDir),
        ('- recon_root: {0}' -f $ReconRoot),
        ('- psf_mode: ckpt_embedded'),
        ('- device: {0}' -f $Device)
    )
    $lines | ForEach-Object { Write-Host $_ }
}

if ($FormalInferAction -eq 'show-recipe') {
    $effectiveInputDir = if ([string]::IsNullOrWhiteSpace($FormalInferInputDir)) { '<not set>' } else { $FormalInferInputDir }
    $effectiveReconRoot = if ([string]::IsNullOrWhiteSpace($FormalInferReconRoot)) { '<not set>' } else { $FormalInferReconRoot }
    Show-FormalR26InferSummary -InputDir $effectiveInputDir -ReconRoot $effectiveReconRoot -Device $FormalInferDevice
}
elseif ($FormalInferAction -eq 'dry-run-demo' -or $FormalInferAction -eq 'dry-run-custom') {
    $payload = [pscustomobject]@{
        recipe_path = $FormalInferRecipePath
        script_path = $FormalInferScriptPath
        native_args = (Get-FormalR26InferNativeArgs -InputDir $FormalInferInputDir -ReconRoot $FormalInferReconRoot -Device $FormalInferDevice)
        docker_command = (Get-FormalR26InferDockerCommand -InputDir $FormalInferInputDir -ReconRoot $FormalInferReconRoot -Device $FormalInferDevice)
    }
    $payload | ConvertTo-Json -Depth 6
}
