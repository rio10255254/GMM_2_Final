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
    $required = @(
        (Join-Path $PathText 'START_HERE.bat'),
        (Join-Path $PathText '內部檔案\GeoEdge_AutoLauncher.ps1'),
        (Join-Path $PathText '內部檔案\GeoEdge_NativeLauncher.ps1')
    )
    foreach ($item in $required) {
        if (-not (Test-Path -LiteralPath $item)) {
            return $false
        }
    }
    return $true
}

function Resolve-TargetPackageRoot([string]$InputPath) {
    if (-not [string]::IsNullOrWhiteSpace($InputPath)) {
        return $InputPath
    }

    $candidates = @(
        (Join-Path (Split-Path -Parent $PSScriptRoot) 'GeoEdge_R26_使用包'),
        (Split-Path -Parent $PSScriptRoot)
    )
    foreach ($candidate in $candidates) {
        if (Test-IsGeoEdgePackage -PathText $candidate) {
            return $candidate
        }
    }

    return ''
}

$resolvedTarget = Resolve-TargetPackageRoot -InputPath $TargetPackageRoot
if ([string]::IsNullOrWhiteSpace($resolvedTarget)) {
    $resolvedTarget = Read-Host 'Enter target package root path (contains START_HERE.bat)'
}

if (-not (Test-IsGeoEdgePackage -PathText $resolvedTarget)) {
    throw ("Invalid target package root: {0}" -f $resolvedTarget)
}

$targetRoot = (Resolve-Path -LiteralPath $resolvedTarget).Path
$targetInternal = Join-Path $targetRoot '內部檔案'
$targetRuntime = Join-Path $targetInternal 'portable_runtime'
$targetRuntimeZip = Join-Path $targetInternal 'portable_runtime_bundle.zip'
$targetRuntimeState = Join-Path $targetRuntime '.geoedge_portable_runtime.json'

$payloadInternal = Join-Path $PSScriptRoot 'payload\內部檔案'
$payloadRuntime = Join-Path $payloadInternal 'portable_runtime'
$payloadRuntimeZip = Join-Path $payloadInternal 'portable_runtime_bundle.zip'

if ((-not (Test-Path -LiteralPath $payloadRuntime)) -and (-not (Test-Path -LiteralPath $payloadRuntimeZip))) {
    throw 'GPU patch payload is missing portable runtime data.'
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupRoot = Join-Path $targetInternal ('gpu_patch_backup_' + $timestamp)

if ((Test-Path -LiteralPath $targetRuntime) -or (Test-Path -LiteralPath $targetRuntimeZip)) {
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    if (Test-Path -LiteralPath $targetRuntime) {
        Move-Item -LiteralPath $targetRuntime -Destination (Join-Path $backupRoot 'portable_runtime')
    }
    if (Test-Path -LiteralPath $targetRuntimeZip) {
        Move-Item -LiteralPath $targetRuntimeZip -Destination (Join-Path $backupRoot 'portable_runtime_bundle.zip')
    }
}

if (Test-Path -LiteralPath $payloadRuntime) {
    Copy-Item -LiteralPath $payloadRuntime -Destination $targetRuntime -Recurse -Force
}
if (Test-Path -LiteralPath $payloadRuntimeZip) {
    Copy-Item -LiteralPath $payloadRuntimeZip -Destination $targetRuntimeZip -Force
}

if (-not (Test-Path -LiteralPath (Join-Path $targetRuntime 'python.exe'))) {
    throw ('Patch apply failed: python.exe not found at {0}' -f $targetRuntime)
}

$stateJson = (@{
    portable_root = $targetRuntime
    fixed_at = (Get-Date).ToString('o')
} | ConvertTo-Json -Depth 4)
[System.IO.File]::WriteAllText(
    $targetRuntimeState,
    $stateJson,
    (New-Object System.Text.UTF8Encoding($true))
)

Write-Host ''
Write-Host '[OK] GPU runtime patch installed.'
Write-Host ('Target package: {0}' -f $targetRoot)
if (Test-Path -LiteralPath $backupRoot) {
    Write-Host ('Backup created: {0}' -f $backupRoot)
}
Write-Host 'You can now run START_HERE.bat again.'
