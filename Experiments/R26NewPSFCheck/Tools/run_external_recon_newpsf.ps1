param(
    [string]$PythonExe = "C:\Users\Rio\anaconda3\python.exe",
    [string]$WeightsPath = "",
    [string]$CandidateName = "newpsf_r26_retrain"
)

$ErrorActionPreference = "Stop"

$toolsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sandboxRoot = Split-Path -Parent $toolsRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $sandboxRoot)
$sharedTool = Join-Path $projectRoot "Tools\RunRepresentativeExternalRecon.ps1"

if ([string]::IsNullOrWhiteSpace($WeightsPath)) {
    $WeightsPath = Join-Path $sandboxRoot ("artifacts\" + $CandidateName + "\weights\best_tradeoff.pth.tar")
}

$candidateRoot = Join-Path $sandboxRoot ("external_compare\" + $CandidateName)
$gmfRawRoot = Join-Path $candidateRoot "gmf_results\raw"

New-Item -ItemType Directory -Force -Path (Join-Path $gmfRawRoot "pitch8px") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $gmfRawRoot "pitch0p8px") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $gmfRawRoot "pitch0p08px") | Out-Null

& $sharedTool `
    -WeightsPath $WeightsPath `
    -ReconRoot $candidateRoot `
    -PythonExe $PythonExe

Write-Host "[INFO] External GMF score drop-in targets:"
Write-Host ("  {0}" -f (Join-Path $gmfRawRoot "pitch8px\GMF_score.txt"))
Write-Host ("  {0}" -f (Join-Path $gmfRawRoot "pitch0p8px\GMF_score.txt"))
Write-Host ("  {0}" -f (Join-Path $gmfRawRoot "pitch0p08px\GMF_score.txt"))
