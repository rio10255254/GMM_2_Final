$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ErrorActionPreference = "Stop"

$root = "$ProjectRoot\Traing_Progress\organized_20260311\external_validation\round11_annulus_lock_defect"
$reconRoot = Join-Path $root "reconstructions"
$logRoot = Join-Path $root "logs"
$weights = "$ProjectRoot\Traing_Progress\training_progress_GESR_v1_v5_ST0p08_SWP_ald_20260310_235036\weights\best_tradeoff.pth.tar"
$script = "$ProjectRoot\Model\GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"

$mixedDir = Join-Path $reconRoot "reconstruct_progress_best_tradeoff_in_Cropped_Output_20260310_235036"
if (Test-Path $mixedDir) {
    $ignoreDir = Join-Path $reconRoot "IGNORE_mixed_outputs_20260311"
    if (Test-Path $ignoreDir) {
        Remove-Item -Recurse -Force $ignoreDir
    }
    Move-Item $mixedDir $ignoreDir
}

$jobs = @(
    @{ name = "pitch1um_y_100_odd"; input = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output" },
    @{ name = "pitch0p1um_y_60_odd"; input = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.1um_Y_60\Cropped_Output" },
    @{ name = "pitch0p01um_y_40_odd"; input = "C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch0.01um_Y_40\Cropped_Output" }
)

$results = @()
foreach ($j in $jobs) {
    $outLog = Join-Path $logRoot ($j.name + ".rerun.out.log")
    $errLog = Join-Path $logRoot ($j.name + ".rerun.err.log")
    Write-Host "[RERUN] $($j.name)"
    & python -u $script --weights $weights --input-dir $j.input --recon-root $reconRoot --output-name $j.name --select-mode odd 1> $outLog 2> $errLog
    if ($LASTEXITCODE -ne 0) {
        throw "reconstruction rerun failed: $($j.name)"
    }
    $targetDir = Get-ChildItem -Directory $reconRoot |
        Where-Object { Test-Path (Join-Path $_.FullName $j.name) } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $targetDir) {
        throw "cannot find output folder for $($j.name)"
    }
    $leaf = Join-Path $targetDir.FullName $j.name
    $count = (Get-ChildItem -File $leaf | Measure-Object).Count
    $results += [pscustomobject]@{
        name = $j.name
        input = $j.input
        output_dir = $leaf
        file_count = $count
        out_log = $outLog
        err_log = $errLog
    }
}

$manifest = Join-Path $root "recon_manifest.json"
$results | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $manifest
$results | Format-List
