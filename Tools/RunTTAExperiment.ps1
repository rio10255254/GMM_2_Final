param(
    [string]$TtaMode = "cross5",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$inferScript = Join-Path $projectRoot "Model\GeoEdgeAlignSR_v1_Infer_TTA.py"
$weightsPath = "$ProjectRoot\Traing_Progress\organized_20260316\round26\archive\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r26sm035_20260316_190408\weights\best_tradeoff.pth.tar"
$reconRoot = "$ProjectRoot\Traing_Progress\organized_20260316\tta_experiment\r26_tta_$TtaMode"

$datasets = @(
    @{
        Name = "Pitch1um_Y_100"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output"
        OutputName = "pitch8px"
    },
    @{
        Name = "Pitch0.1um_Y_60"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.1um_Y_60\Cropped_Output"
        OutputName = "pitch0p8px"
    },
    @{
        Name = "Pitch0.01um_Y_40"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.01um_Y_40\Cropped_Output"
        OutputName = "pitch0p08px"
    }
)

$reconRootPath = [System.IO.Path]::GetFullPath($reconRoot)
$weightsFullPath = [System.IO.Path]::GetFullPath($weightsPath)

if (-not (Test-Path $inferScript)) {
    throw "TTA inference script not found: $inferScript"
}
if (-not (Test-Path $weightsFullPath)) {
    throw "Weights not found: $weightsFullPath"
}

New-Item -ItemType Directory -Force -Path $reconRootPath | Out-Null

$manifest = [ordered]@{
    started_at   = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    experiment   = "TTA"
    tta_mode     = $TtaMode
    weights_path = $weightsFullPath
    infer_script = $inferScript
    recon_root   = $reconRootPath
    baseline     = "R26 sm035 (0.8px step_std = 0.191336)"
    datasets     = @()
}

Write-Host "========================================="
Write-Host "TTA Experiment: mode=$TtaMode"
Write-Host "Weights: $weightsFullPath"
Write-Host "Output:  $reconRootPath"
Write-Host "========================================="

foreach ($ds in $datasets) {
    $inputDir = [System.IO.Path]::GetFullPath([string]$ds.InputDir)
    $outputName = [string]$ds.OutputName
    Write-Host ""
    Write-Host ("[RUN] dataset={0}  tta_mode={1}" -f $ds.Name, $TtaMode)
    Write-Host ("[RUN] input={0}" -f $inputDir)
    Write-Host ("[RUN] output_name={0}" -f $outputName)

    & $PythonExe $inferScript `
        --weights $weightsFullPath `
        --input-dir $inputDir `
        --recon-root $reconRootPath `
        --output-name $outputName `
        --select-mode odd `
        --tta-mode $TtaMode

    if ($LASTEXITCODE -ne 0) {
        throw ("TTA inference failed for dataset {0} with exit code {1}" -f $ds.Name, $LASTEXITCODE)
    }
    $manifest.datasets += [ordered]@{
        name       = [string]$ds.Name
        input_dir  = $inputDir
        output_name = $outputName
    }
}

$manifest.completed_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$manifestPath = Join-Path $reconRootPath "batch_manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding utf8

Write-Host ""
Write-Host "========================================="
Write-Host "[DONE] TTA experiment complete"
Write-Host "[DONE] manifest=$manifestPath"
Write-Host "[DONE] Next step: run external GMF on output images, then compare with R26 baseline"
Write-Host "========================================="
