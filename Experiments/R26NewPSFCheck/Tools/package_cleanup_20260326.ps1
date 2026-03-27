param()

$ErrorActionPreference = "Stop"

$pkg = "D:\GMM_2_Final\_deployment_package\GeoEdge_R26_正式交付版\GeoEdge_R26_使用包"
$archive = "D:\GMM_2_Final\Experiments\R26NewPSFCheck\artifacts\package_cleanup_archive_20260326"

New-Item -ItemType Directory -Force -Path $archive | Out-Null

$moves = @(
    @{
        Source = Join-Path $pkg "analysis_single_image_recon"
        Target = Join-Path $archive "analysis_single_image_recon"
    },
    @{
        Source = Join-Path $pkg "analysis_single_image_recon_newpsf"
        Target = Join-Path $archive "analysis_single_image_recon_newpsf"
    },
    @{
        Source = Join-Path $pkg "輸出結果\訓練結果\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223"
        Target = Join-Path $archive "training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223"
    },
    @{
        Source = Join-Path $pkg "輸出結果\推論結果\reconstruct_progress_best_tradeoff_in_Demo_Input_20260326_093223"
        Target = Join-Path $archive "reconstruct_progress_best_tradeoff_in_Demo_Input_20260326_093223"
    },
    @{
        Source = Join-Path $pkg "輸出結果\比較結果\psf_swap_20260326_093203"
        Target = Join-Path $archive "psf_swap_20260326_093203"
    },
    @{
        Source = Join-Path $pkg "輸出結果\比較結果\new_psf_retrain_compare_20260326.md"
        Target = Join-Path $archive "new_psf_retrain_compare_20260326.package_copy.md"
    }
)

foreach ($entry in $moves) {
    if (Test-Path $entry.Source) {
        Move-Item -Force $entry.Source $entry.Target
    }
}

$removePaths = @(
    (Join-Path $pkg ".claude"),
    (Join-Path $pkg ".pytest_cache")
)

foreach ($path in $removePaths) {
    if (Test-Path $path) {
        Remove-Item -Recurse -Force $path
    }
}

$compareDir = Join-Path $pkg "輸出結果\比較結果"
if ((Test-Path $compareDir) -and -not (Get-ChildItem -Force $compareDir)) {
    Remove-Item -Recurse -Force $compareDir
}

Write-Host "=== PACKAGE TOP LEVEL ==="
Get-ChildItem $pkg -Force | Select-Object Name, Mode, LastWriteTime | Format-Table -AutoSize

Write-Host "=== CLEANUP ARCHIVE ==="
Get-ChildItem $archive | Select-Object Name, Mode, LastWriteTime | Format-Table -AutoSize
