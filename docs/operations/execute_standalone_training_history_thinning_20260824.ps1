param(
    [switch]$Execute
)
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = $ProjectRoot
$summaryPath = Join-Path $repoRoot 'docs\operations\STANDALONE_TRAINING_HISTORY_EXECUTION_20260824.json'
$planPath = Join-Path $repoRoot 'docs\operations\STANDALONE_TRAINING_HISTORY_DELETE_PLAN_20260824.csv'
$summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
$plan = @(Import-Csv -LiteralPath $planPath)
if ($summary.status -ne 'predelete_exact_targets_verified') {
    throw "Unexpected execution status: $($summary.status)"
}
if ($plan.Count -ne [int]$summary.planned_removal.directories) {
    throw 'Plan row count mismatch.'
}

$sourceRoot = [IO.Path]::GetFullPath($summary.source_root).TrimEnd('\')
$sourcePrefix = $sourceRoot + '\'
$relatedProcesses = @(
    Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and
        $_.CommandLine -and
        $_.CommandLine -match 'GMM_2_Final' -and
        $_.CommandLine -match '(?i)train|reconstruct|evaluate|inference|pytest|matlab|git.*(gc|repack|fetch|pack)'
    }
)
if ($relatedProcesses.Count -ne 0) {
    throw 'A related project process is active.'
}

$verified = @()
foreach ($target in $plan) {
    $name = [string]$target.name
    if ([System.Management.Automation.WildcardPattern]::ContainsWildcardCharacters($name) -or
        $name -match '[\\/]') {
        throw "Invalid direct-child name: $name"
    }
    $allowed = (
        $name -match '(?i)_r32' -or
        $name -match '(?i)_FIN_r(?:25|26|27|28|29|31)' -or
        $name -match '(?i)process_probe_r(?:28|30|32)' -or
        $name -match '(?i)_r38v2_.*ABLA_' -or
        $name -match '(?i)_r42_' -or
        $name -match '(?i)_r44' -or
        $name -match '(?i)_r46_'
    )
    if (-not $allowed -or $name -match '^training_progress_GeoEdgeAlignSR') {
        throw "Name is outside the approved closed-run classes: $name"
    }
    $fullPath = [IO.Path]::GetFullPath((Join-Path $sourceRoot $name))
    if (-not $fullPath.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target is outside Traing_Progress: $fullPath"
    }
    if (-not (Test-Path -LiteralPath $fullPath -PathType Container)) {
        throw "Target is missing: $fullPath"
    }
    $items = @(Get-ChildItem -LiteralPath $fullPath -Recurse -Force)
    $links = @($items | Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 })
    if ($links.Count -ne 0) {
        throw "Target contains a reparse point: $fullPath"
    }
    $files = @($items | Where-Object { -not $_.PSIsContainer })
    [int64]$bytes = ($files | Measure-Object -Property Length -Sum).Sum
    if ($files.Count -ne [int]$target.files -or $bytes -ne [int64]$target.bytes) {
        throw "Target changed after approval: $fullPath"
    }
    $verified += [pscustomobject]@{
        name = $name
        full_path = $fullPath
        files = $files.Count
        logical_bytes = $bytes
    }
}

$totalFiles = ($verified | Measure-Object -Property files -Sum).Sum
[int64]$totalBytes = ($verified | Measure-Object -Property logical_bytes -Sum).Sum
if ($totalFiles -ne [int]$summary.planned_removal.files -or
    $totalBytes -ne [int64]$summary.planned_removal.logical_bytes) {
    throw 'Combined target totals do not match the approved summary.'
}

if (-not $Execute) {
    [ordered]@{
        status = 'DRY_RUN_PASS'
        directories = $verified.Count
        files = $totalFiles
        logical_bytes = $totalBytes
        related_processes = 0
        targets = $verified
    } | ConvertTo-Json -Depth 5
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
        name = $target.name
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
    removed = $removed
} | ConvertTo-Json -Depth 5
