param(
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = 'D:\GMM_2_Final'
$planPath = Join-Path $repoRoot 'docs\operations\LEGACY_R16_R31_ARCHIVE_DELETE_PLAN_20260824.json'
$plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
if ($plan.status -ne 'prearchive_exact_targets_verified') {
    throw "Unexpected plan status: $($plan.status)"
}

$sourceRoot = [IO.Path]::GetFullPath($plan.source_root).TrimEnd('\')
$sourcePrefix = $sourceRoot + '\'
$relatedProcesses = @(
    Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and
        $_.CommandLine -and
        $_.CommandLine -match 'D:\\GMM_2_Final|GMM_2_Final' -and
        $_.CommandLine -match '(?i)train|reconstruct|evaluate|inference|pytest|matlab|git.*(gc|repack|fetch|pack)'
    }
)
if ($relatedProcesses.Count -ne 0) {
    throw 'A related project process is active.'
}

$verified = @()
foreach ($target in $plan.targets) {
    $batch = [string]$target.batch
    $relativePath = ([string]$target.path).Replace('/', '\')
    if ([System.Management.Automation.WildcardPattern]::ContainsWildcardCharacters($relativePath)) {
        throw "Wildcard target is forbidden: $relativePath"
    }
    $batchRoot = [IO.Path]::GetFullPath((Join-Path $sourceRoot $batch)).TrimEnd('\')
    $batchPrefix = $batchRoot + '\'
    $fullPath = [IO.Path]::GetFullPath((Join-Path $batchRoot $relativePath))
    if (-not $fullPath.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target is outside Traing_Progress: $fullPath"
    }
    if (-not $fullPath.StartsWith($batchPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target is outside its declared batch: $fullPath"
    }
    if ($fullPath -match '(?i)[\\/](selected|pending|reports|gmf_results|root_status_legacy)([\\/]|$)') {
        throw "Protected retention surface is in the removal plan: $fullPath"
    }
    if (-not (Test-Path -LiteralPath $fullPath -PathType Container)) {
        throw "Target is missing: $fullPath"
    }
    $items = @(Get-ChildItem -LiteralPath $fullPath -Recurse -Force)
    $links = @(
        $items | Where-Object {
            ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        }
    )
    if ($links.Count -ne 0) {
        throw "Target contains a reparse point: $fullPath"
    }
    $files = @($items | Where-Object { -not $_.PSIsContainer })
    [int64]$bytes = ($files | Measure-Object -Property Length -Sum).Sum
    if ($files.Count -ne [int]$target.files -or $bytes -ne [int64]$target.bytes) {
        throw "Target changed after approval: $fullPath"
    }
    $verified += [pscustomobject]@{
        batch = $batch
        relative_path = ([string]$target.path)
        full_path = $fullPath
        files = $files.Count
        logical_bytes = $bytes
    }
}

$totalFiles = ($verified | Measure-Object -Property files -Sum).Sum
[int64]$totalBytes = ($verified | Measure-Object -Property logical_bytes -Sum).Sum
if ($verified.Count -ne [int]$plan.planned_removal_summary.directories -or
    $totalFiles -ne [int]$plan.planned_removal_summary.files -or
    $totalBytes -ne [int64]$plan.planned_removal_summary.logical_bytes) {
    throw 'Combined target totals do not match the approved plan.'
}

if (-not $Execute) {
    [ordered]@{
        status = 'DRY_RUN_PASS'
        directories = $verified.Count
        files = $totalFiles
        logical_bytes = $totalBytes
        related_processes = 0
        targets = $verified
    } | ConvertTo-Json -Depth 6
    exit 0
}

$dFreeBefore = [IO.DriveInfo]::new('D').AvailableFreeSpace
$hFreeBefore = [IO.DriveInfo]::new('H').AvailableFreeSpace
$removed = @()
foreach ($target in $verified) {
    Remove-Item -LiteralPath $target.full_path -Recurse -Force -ErrorAction Stop
    if (Test-Path -LiteralPath $target.full_path) {
        throw "Removal did not complete: $($target.full_path)"
    }
    $removed += [pscustomobject]@{
        batch = $target.batch
        relative_path = $target.relative_path
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
    directories_removed = $removed.Count
    files_removed = ($removed | Measure-Object -Property files -Sum).Sum
    logical_bytes_removed = ($removed | Measure-Object -Property logical_bytes -Sum).Sum
    d_free_bytes_before = $dFreeBefore
    d_free_bytes_after = $dFreeAfter
    actual_d_reclaimed_bytes = $dFreeAfter - $dFreeBefore
    h_free_bytes_before = $hFreeBefore
    h_free_bytes_after = $hFreeAfter
    retained_surfaces = 'selected, pending, reports, postmortems, README, MANIFEST, GMF scores and restore pointers'
    removed = $removed
} | ConvertTo-Json -Depth 6
