param(
    [switch]$Execute
)
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')).Path

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$labRoot = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR')
$rootPrefix = [IO.Path]::GetFullPath($labRoot).TrimEnd('\') + '\'
$targets = @(
    [pscustomobject]@{
        id = 'training_data'
        path = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r52_corner_stability_guard')
        files = 23502
        bytes = [int64]9881861535
    },
    [pscustomobject]@{
        id = 'run_formal'
        path = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r52_stability_from_r51_mixed_best_formal_e100_20260614_225415')
        files = 60
        bytes = [int64]1742280373
    },
    [pscustomobject]@{
        id = 'run_smoke'
        path = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r52_stability_from_r51_mixed_best_smoke_e001_b001_20260614_225229')
        files = 20
        bytes = [int64]280603817
    },
    [pscustomobject]@{
        id = 'corner_validation'
        path = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\corner_geometry_validation_r52_20260615')
        files = 11
        bytes = [int64]2157746
    },
    [pscustomobject]@{
        id = 'reconstruction_outputs'
        path = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\r52_reconstruction_outputs')
        files = 102
        bytes = [int64]320974212
    },
    [pscustomobject]@{
        id = 'gmf_best_tradeoff'
        path = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\gmf_cases\lab_r52_stability_best_tradeoff')
        files = 51
        bytes = [int64]160487106
    },
    [pscustomobject]@{
        id = 'gmf_latest'
        path = (Join-Path $ProjectRoot 'Thesis_MOSR_Evidence\LabSystem_MOSR\Reconstruct_Progress\20250605_checkboard_external_gmf_prepare\gmf_cases\lab_r52_stability_latest')
        files = 51
        bytes = [int64]160487106
    }
)

$relatedProcesses = @(
    Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and
        $_.CommandLine -and
        $_.CommandLine -match 'GMM_2_Final' -and
        $_.CommandLine -match '(?i)train|reconstruct|evaluate|inference|pytest|matlab'
    }
)
if ($relatedProcesses.Count -ne 0) {
    throw 'A related training, reconstruction, evaluation, test, or MATLAB process is active.'
}

$verified = @()
foreach ($target in $targets) {
    if ([System.Management.Automation.WildcardPattern]::ContainsWildcardCharacters($target.path)) {
        throw "Wildcard target is forbidden: $($target.path)"
    }
    $fullPath = [IO.Path]::GetFullPath($target.path)
    if (-not $fullPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target is outside the LabSystem root: $fullPath"
    }
    if ($fullPath -match '(?i)[\\/]R(?:8[7-9]|9[0-5])(?:_|[\\/]|$)') {
        throw "Target intersects protected R87-R95 content: $fullPath"
    }
    if (-not (Test-Path -LiteralPath $fullPath -PathType Container)) {
        throw "Target is missing: $fullPath"
    }
    $items = @(Get-ChildItem -LiteralPath $fullPath -Recurse -Force)
    $reparsePoints = @(
        $items | Where-Object {
            ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        }
    )
    if ($reparsePoints.Count -ne 0) {
        throw "Target contains a reparse point: $fullPath"
    }
    $files = @($items | Where-Object { -not $_.PSIsContainer })
    [int64]$bytes = ($files | Measure-Object -Property Length -Sum).Sum
    if ($files.Count -ne $target.files -or $bytes -ne $target.bytes) {
        throw "Target changed after approval: $fullPath"
    }
    $verified += [pscustomobject]@{
        id = $target.id
        path = $fullPath
        files = $files.Count
        logical_bytes = $bytes
    }
}

if (-not $Execute) {
    [ordered]@{
        status = 'DRY_RUN_PASS'
        targets = $verified
        related_processes = 0
    } | ConvertTo-Json -Depth 5
    exit 0
}

$dFreeBefore = [IO.DriveInfo]::new('D').AvailableFreeSpace
$hFreeBefore = [IO.DriveInfo]::new('H').AvailableFreeSpace
$removed = @()
foreach ($target in $verified) {
    Remove-Item -LiteralPath $target.path -Recurse -Force -ErrorAction Stop
    if (Test-Path -LiteralPath $target.path) {
        throw "Removal did not complete: $($target.path)"
    }
    $removed += [pscustomobject]@{
        id = $target.id
        path = $target.path
        files = $target.files
        logical_bytes = $target.logical_bytes
        absent_after_removal = $true
    }
}

Start-Sleep -Seconds 2
$dFreeAfter = [IO.DriveInfo]::new('D').AvailableFreeSpace
$hFreeAfter = [IO.DriveInfo]::new('H').AvailableFreeSpace
[ordered]@{
    status = 'REMOVAL_COMPLETE'
    removed_at = (Get-Date).ToString('o')
    targets = $removed
    directories_removed = $removed.Count
    files_removed = ($removed | Measure-Object -Property files -Sum).Sum
    logical_bytes_removed = ($removed | Measure-Object -Property logical_bytes -Sum).Sum
    d_free_bytes_before = $dFreeBefore
    d_free_bytes_after = $dFreeAfter
    actual_d_reclaimed_bytes = $dFreeAfter - $dFreeBefore
    h_free_bytes_before = $hFreeBefore
    h_free_bytes_after = $hFreeAfter
    canonical_experiment_present = Test-Path -LiteralPath (Join-Path $labRoot 'Experiments\R52_CornerStabilityGuard')
    protected_R87_R95_touched = $false
} | ConvertTo-Json -Depth 6
