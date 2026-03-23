param(
    [string]$PythonExe = "C:\Users\Rio\anaconda3\python.exe",
    [string]$DecisionJson = "",
    [string]$WeightsPath = "",
    [string]$CandidateName = ""
)

$ErrorActionPreference = "Stop"

$toolsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sandboxRoot = Split-Path -Parent $toolsRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $sandboxRoot)
$reportRoot = Join-Path $sandboxRoot "reports"
$compareScript = Join-Path $sandboxRoot "Model\external_gmf_round32_compare.py"
$inferScript = Join-Path $projectRoot "Model\GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"

if ([string]::IsNullOrWhiteSpace($DecisionJson)) {
    $DecisionJson = Get-ChildItem -Path $reportRoot -Filter "ROUND32_DOMAIN_CAPACITY_DECISION_*.json" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $DecisionJson) {
    throw "No ROUND32 decision JSON found under $reportRoot"
}

$decision = Get-Content -Raw $DecisionJson | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($WeightsPath)) {
    $WeightsPath = [string]$decision.selected_checkpoint
}
if ([string]::IsNullOrWhiteSpace($CandidateName)) {
    $CandidateName = [string]$decision.selected_candidate
}
if (-not $WeightsPath) {
    throw "No selected checkpoint found in $DecisionJson"
}
if (-not $CandidateName) {
    throw "No selected candidate found in $DecisionJson"
}

$candidateRoot = Join-Path $sandboxRoot ("external_compare\" + $CandidateName)
$reconRoot = Join-Path $candidateRoot "reconstructions"
$gmfRawRoot = Join-Path $candidateRoot ("gmf_results\raw\" + $CandidateName)

$datasets = @(
    @{
        Name = "Pitch1um_Y_100"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output"
        OutputName = "pitch1um_y_100_odd"
        GmfPitchDir = "pitch8px"
    },
    @{
        Name = "Pitch0.1um_Y_60"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.1um_Y_60\Cropped_Output"
        OutputName = "pitch0p1um_y_60_odd"
        GmfPitchDir = "pitch0p8px"
    },
    @{
        Name = "Pitch0.01um_Y_40"
        InputDir = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.01um_Y_40\Cropped_Output"
        OutputName = "pitch0p01um_y_40_odd"
        GmfPitchDir = "pitch0p08px"
    }
)

New-Item -ItemType Directory -Force -Path $reconRoot | Out-Null
foreach ($ds in $datasets) {
    New-Item -ItemType Directory -Force -Path (Join-Path $gmfRawRoot $ds.GmfPitchDir) | Out-Null
}

$manifest = [ordered]@{
    generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    decision_json = [System.IO.Path]::GetFullPath($DecisionJson)
    candidate = $CandidateName
    weights_path = [System.IO.Path]::GetFullPath($WeightsPath)
    infer_script = [System.IO.Path]::GetFullPath($inferScript)
    compare_script = [System.IO.Path]::GetFullPath($compareScript)
    candidate_root = [System.IO.Path]::GetFullPath($candidateRoot)
    recon_root = [System.IO.Path]::GetFullPath($reconRoot)
    gmf_raw_root = [System.IO.Path]::GetFullPath($gmfRawRoot)
    datasets = @()
}

foreach ($ds in $datasets) {
    $inputDir = [System.IO.Path]::GetFullPath([string]$ds.InputDir)
    Write-Host ("[RUN] dataset={0}" -f $ds.Name)
    & $PythonExe $inferScript `
        --weights $WeightsPath `
        --input-dir $inputDir `
        --recon-root $reconRoot `
        --output-name $ds.OutputName `
        --select-mode odd
    if ($LASTEXITCODE -ne 0) {
        throw ("Inference failed for dataset {0} with exit code {1}" -f $ds.Name, $LASTEXITCODE)
    }
    $manifest.datasets += [ordered]@{
        name = [string]$ds.Name
        input_dir = $inputDir
        output_name = [string]$ds.OutputName
        expected_gmf_score = Join-Path (Join-Path $gmfRawRoot $ds.GmfPitchDir) "GMF_score.txt"
    }
}

$manifest.completed_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$manifestPath = Join-Path $candidateRoot "batch_manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding utf8
Write-Host ("[DONE] manifest={0}" -f $manifestPath)
