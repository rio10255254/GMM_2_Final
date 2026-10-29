param(
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ExperimentRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$LabRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path.TrimEnd('\')
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $LabRoot '..\..')).Path
$PlanPath = Join-Path $ExperimentRoot 'ARCHIVE_DELETE_PLAN_R49_20260809.json'
$ScopePath = Join-Path $ExperimentRoot 'ARCHIVE_SCOPE_R49_20260809.json'
$Python = python
$Guard = Join-Path $RepoRoot 'Tools\project_storage_guard.py'
$Snapshot = 'H:\GMM_2_Final_Archive\lab_system\R49_CADAnchorRealGeometry\20260809_full_history\snapshot'
$ManifestRoot = 'H:\GMM_2_Final_Archive\manifests'

foreach ($required in @($PlanPath, $ScopePath, $Python, $Guard, $Snapshot, $ManifestRoot)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required cleanup input is missing: $required"
    }
}

$auditOutput = & $Python $Guard lifecycle-audit 2>&1
if ($LASTEXITCODE -ne 0 -or (($auditOutput -join "`n") -notmatch 'Bulk actions: READY')) {
    throw "Lifecycle guard is not ready:`n$($auditOutput -join "`n")"
}

$projectCompute = @(
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^(python|pythonw|matlab|MATLAB|pytest)\.exe$' -and
        $_.CommandLine -and
        ($_.CommandLine -match ([regex]::Escape($RepoRoot) + '|' + [regex]::Escape($RepoRoot.Replace('\', '/')) + '|train_r84\.py|infer_r84\.py|run_acm_multimethod|run_sem_acm_selected_pillars|reconstruct'))
    }
)
if ($projectCompute.Count -ne 0) {
    $details = $projectCompute | Select-Object ProcessId, ParentProcessId, Name, CommandLine | ConvertTo-Json -Compress
    throw "A project compute process became active: $details"
}

$scope = Get-Content -LiteralPath $ScopePath -Raw | ConvertFrom-Json
$plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json

foreach ($source in $scope.sources) {
    $manifest = Join-Path $ManifestRoot ("Lab_R49_{0}_20260809.csv" -f $source.id)
    $destination = Join-Path $Snapshot ($source.path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
        throw "A verified SHA-256 manifest is missing: $manifest"
    }
    if (-not (Test-Path -LiteralPath $destination -PathType Container)) {
        throw "An H-drive snapshot source is missing: $destination"
    }
}

$tracked = @(& git -C $RepoRoot ls-files -- 'Thesis_MOSR_Evidence/LabSystem_MOSR')
$validated = @()
$totalFiles = [int64]0
$totalBytes = [int64]0

foreach ($relative in $plan.exact_targets) {
    $absolute = [System.IO.Path]::GetFullPath((Join-Path $LabRoot ($relative -replace '/', '\')))
    if (-not $absolute.StartsWith($LabRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing a target outside the Lab-system root: $absolute"
    }
    if (-not (Test-Path -LiteralPath $absolute)) {
        throw "A planned target no longer exists: $absolute"
    }

    $item = Get-Item -LiteralPath $absolute -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing a reparse-point target: $absolute"
    }

    $repositoryRelative = ('Thesis_MOSR_Evidence/LabSystem_MOSR/' + $relative).Replace('\', '/')
    $overlap = @(
        $tracked | Where-Object {
            $_ -eq $repositoryRelative -or
            $_.StartsWith($repositoryRelative + '/', [System.StringComparison]::OrdinalIgnoreCase)
        }
    )
    if ($overlap.Count -ne 0) {
        throw "A planned target overlaps Git-tracked content: $relative"
    }

    if ($item.PSIsContainer) {
        $files = @(Get-ChildItem -LiteralPath $absolute -Recurse -File -Force)
        $fileCount = $files.Count
        $bytes = [int64](($files | Measure-Object Length -Sum).Sum)
    }
    else {
        $fileCount = 1
        $bytes = [int64]$item.Length
    }

    $totalFiles += $fileCount
    $totalBytes += $bytes
    $validated += [pscustomobject]@{
        relative = $relative
        absolute = $absolute
        is_directory = [bool]$item.PSIsContainer
        files = $fileCount
        bytes = $bytes
    }
}

if (
    $validated.Count -ne [int]$plan.summary.target_count -or
    $totalFiles -ne [int64]$plan.summary.file_count -or
    $totalBytes -ne [int64]$plan.summary.bytes
) {
    throw "The final target scope drifted: targets=$($validated.Count), files=$totalFiles, bytes=$totalBytes"
}

$driveBefore = Get-PSDrive -Name D
$beforeBytes = [int64]$driveBefore.Free
$beforeTime = (Get-Date).ToString('o')

if (-not $Execute) {
    [ordered]@{
        status = 'DRY_RUN_PASS'
        checked_at = $beforeTime
        targets = $validated.Count
        files = $totalFiles
        bytes = $totalBytes
        gib = [math]::Round($totalBytes / 1GB, 4)
        tracked_overlap = 0
        project_compute_processes = 0
        d_free_bytes = $beforeBytes
        d_free_gib = [math]::Round($beforeBytes / 1GB, 4)
    } | ConvertTo-Json
    exit 0
}

foreach ($target in $validated) {
    if ($target.is_directory) {
        Remove-Item -LiteralPath $target.absolute -Recurse -Force -ErrorAction Stop
    }
    else {
        Remove-Item -LiteralPath $target.absolute -Force -ErrorAction Stop
    }
}

$remaining = @($validated | Where-Object { Test-Path -LiteralPath $_.absolute })
if ($remaining.Count -ne 0) {
    throw "Deletion verification failed; $($remaining.Count) exact targets remain."
}

$driveAfter = Get-PSDrive -Name D
$afterBytes = [int64]$driveAfter.Free

[ordered]@{
    status = 'EXECUTION_PASS'
    deleted_at = (Get-Date).ToString('o')
    d_free_before_recorded_at = $beforeTime
    deleted_targets = $validated.Count
    deleted_files = $totalFiles
    logical_deleted_bytes = $totalBytes
    logical_deleted_gib = [math]::Round($totalBytes / 1GB, 4)
    remaining_targets = $remaining.Count
    d_free_before_bytes = $beforeBytes
    d_free_before_gib = [math]::Round($beforeBytes / 1GB, 4)
    d_free_after_bytes = $afterBytes
    d_free_after_gib = [math]::Round($afterBytes / 1GB, 4)
    actual_reclaimed_bytes = $afterBytes - $beforeBytes
    actual_reclaimed_gib = [math]::Round(($afterBytes - $beforeBytes) / 1GB, 4)
} | ConvertTo-Json
