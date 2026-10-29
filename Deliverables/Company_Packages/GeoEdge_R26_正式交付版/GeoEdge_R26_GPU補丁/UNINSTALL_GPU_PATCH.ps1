param(
    [string]$TargetPackageRoot = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-IsGeoEdgePackage([string]$PathText) {
    if ([string]::IsNullOrWhiteSpace($PathText)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $PathText)) {
        return $false
    }
    return (Test-Path -LiteralPath (Join-Path $PathText 'START_HERE.bat')) -and (Test-Path -LiteralPath (Join-Path $PathText '內部檔案\GeoEdge_NativeLauncher.ps1'))
}

if ([string]::IsNullOrWhiteSpace($TargetPackageRoot)) {
    $TargetPackageRoot = Read-Host 'Enter target package root path (contains START_HERE.bat)'
}

if (-not (Test-IsGeoEdgePackage -PathText $TargetPackageRoot)) {
    throw ("Invalid target package root: {0}" -f $TargetPackageRoot)
}

$targetRoot = (Resolve-Path -LiteralPath $TargetPackageRoot).Path
$targetInternal = Join-Path $targetRoot '內部檔案'
$targetRuntime = Join-Path $targetInternal 'portable_runtime'
$targetRuntimeZip = Join-Path $targetInternal 'portable_runtime_bundle.zip'

if (Test-Path -LiteralPath $targetRuntime) {
    Remove-Item -LiteralPath $targetRuntime -Recurse -Force
}
if (Test-Path -LiteralPath $targetRuntimeZip) {
    Remove-Item -LiteralPath $targetRuntimeZip -Force
}

$latestBackup = Get-ChildItem -LiteralPath $targetInternal -Directory -Filter 'gpu_patch_backup_*' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($latestBackup) {
    $backupRuntime = Join-Path $latestBackup.FullName 'portable_runtime'
    $backupRuntimeZip = Join-Path $latestBackup.FullName 'portable_runtime_bundle.zip'
    if (Test-Path -LiteralPath $backupRuntime) {
        Move-Item -LiteralPath $backupRuntime -Destination $targetRuntime
    }
    if (Test-Path -LiteralPath $backupRuntimeZip) {
        Move-Item -LiteralPath $backupRuntimeZip -Destination $targetRuntimeZip
    }
    Write-Host ('[OK] Restored from backup: {0}' -f $latestBackup.FullName)
}
else {
    Write-Host '[OK] GPU runtime removed. No backup found to restore.'
}
