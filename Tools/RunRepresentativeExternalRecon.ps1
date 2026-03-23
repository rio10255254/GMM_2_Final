param(
    [Parameter(Mandatory = $true)]
    [string]$WeightsPath,
    [Parameter(Mandatory = $true)]
    [string]$ReconRoot,
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$inferScript = Join-Path $projectRoot "Model\GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"

$datasets = @(
    @{
        Name = "Pitch1um_Y_100"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output"
        OutputName = "pitch1um_y_100_odd"
    },
    @{
        Name = "Pitch0.1um_Y_60"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.1um_Y_60\Cropped_Output"
        OutputName = "pitch0p1um_y_60_odd"
    },
    @{
        Name = "Pitch0.01um_Y_40"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.01um_Y_40\Cropped_Output"
        OutputName = "pitch0p01um_y_40_odd"
    }
)

$reconRootPath = [System.IO.Path]::GetFullPath($ReconRoot)
$weightsFullPath = [System.IO.Path]::GetFullPath($WeightsPath)

New-Item -ItemType Directory -Force -Path $reconRootPath | Out-Null

$manifest = [ordered]@{
    started_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    weights_path = $weightsFullPath
    infer_script = $inferScript
    recon_root = $reconRootPath
    datasets = @()
}

foreach ($ds in $datasets) {
    $inputDir = [System.IO.Path]::GetFullPath([string]$ds.InputDir)
    $outputName = [string]$ds.OutputName
    Write-Host ("[RUN] dataset={0}" -f $ds.Name)
    Write-Host ("[RUN] input={0}" -f $inputDir)
    Write-Host ("[RUN] output_name={0}" -f $outputName)
    & $PythonExe $inferScript `
        --weights $weightsFullPath `
        --input-dir $inputDir `
        --recon-root $reconRootPath `
        --output-name $outputName `
        --select-mode odd
    if ($LASTEXITCODE -ne 0) {
        throw ("Inference failed for dataset {0} with exit code {1}" -f $ds.Name, $LASTEXITCODE)
    }
    $manifest.datasets += [ordered]@{
        name = [string]$ds.Name
        input_dir = $inputDir
        output_name = $outputName
    }
}

$manifest.completed_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$manifestPath = Join-Path $reconRootPath "batch_manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestPath -Encoding utf8
Write-Host ("[DONE] manifest={0}" -f $manifestPath)
