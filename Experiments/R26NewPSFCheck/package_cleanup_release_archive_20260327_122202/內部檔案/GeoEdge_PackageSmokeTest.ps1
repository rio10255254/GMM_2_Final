param(
    [int]$InferenceSampleCount = 8,
    [int]$QuickTrainEpochs = 1,
    [switch]$SkipTrain
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptRoot
$LauncherPath = Join-Path $ScriptRoot 'GeoEdge_NativeLauncher.ps1'
$ConfigPath = Join-Path $ScriptRoot 'NATIVE_LAUNCHER_CONFIG.json'
$TempRoot = Join-Path $env:TEMP ('geoedge_smoketest_' + [guid]::NewGuid().ToString('N'))
$SubsetDir = Join-Path $TempRoot 'input_subset'
$DemoReconRoot = Join-Path $PackageRoot '輸出結果\推論結果\_smoketest_demo'
$CustomReconRoot = Join-Path $PackageRoot '輸出結果\推論結果\_smoketest_custom'
$TrainRoot = Join-Path $PackageRoot '輸出結果\訓練結果'
$originalConfig = Get-Content -LiteralPath $ConfigPath -Raw

function Write-Utf8BomFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $encoding = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Invoke-LauncherAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Action,
        [string]$InputDir
    )

    $args = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $LauncherPath,
        '-Action', $Action
    )
    if ($InputDir) {
        $args += @('-InputDir', $InputDir)
    }

    & powershell.exe @args
    if ($LASTEXITCODE -ne 0) {
        throw ("launcher action failed: {0}" -f $Action)
    }
}

function Get-LatestChildDirectory([string]$RootPath) {
    if (-not (Test-Path -LiteralPath $RootPath)) {
        return $null
    }

    return (Get-ChildItem -LiteralPath $RootPath -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
}

try {
    New-Item -ItemType Directory -Force -Path $SubsetDir, $DemoReconRoot, $CustomReconRoot, $TrainRoot | Out-Null

    $sampleFiles = @(Get-ChildItem -LiteralPath (Join-Path $ScriptRoot 'Demo_Input') -Filter *.bmp |
        Sort-Object Name |
        Select-Object -First ([Math]::Max(1, $InferenceSampleCount)))
    $sampleCount = @($sampleFiles).Count
    if (-not $sampleFiles) {
        throw '找不到 smoke test 用的示範影像。'
    }
    foreach ($file in $sampleFiles) {
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $SubsetDir $file.Name) -Force
    }

    $cfg = $originalConfig | ConvertFrom-Json
    $cfg.demo_input_dir = $SubsetDir
    $cfg.demo_recon_root = $DemoReconRoot
    $cfg.train_progress_root = $TrainRoot
    $cfg.train_quick_simpletest_max_epoch = [Math]::Max(1, $QuickTrainEpochs)
    Write-Utf8BomFile -Path $ConfigPath -Content (($cfg | ConvertTo-Json -Depth 6))

    Invoke-LauncherAction -Action 'first-run'
    Invoke-LauncherAction -Action 'infer-demo'

    $demoDir = Get-LatestChildDirectory -RootPath $DemoReconRoot
    if (-not $demoDir) {
        throw 'demo inference 沒有產生輸出資料夾。'
    }
    $demoCount = (Get-ChildItem -LiteralPath $demoDir.FullName -File | Measure-Object).Count
    if ($demoCount -lt $sampleCount) {
        throw ("demo inference 輸出張數不足：expected>={0}, actual={1}" -f $sampleCount, $demoCount)
    }

    $cfg = (Get-Content -LiteralPath $ConfigPath -Raw) | ConvertFrom-Json
    $cfg.demo_recon_root = $CustomReconRoot
    Write-Utf8BomFile -Path $ConfigPath -Content (($cfg | ConvertTo-Json -Depth 6))

    Invoke-LauncherAction -Action 'infer-custom' -InputDir $SubsetDir

    $customDir = Get-LatestChildDirectory -RootPath $CustomReconRoot
    if (-not $customDir) {
        throw 'custom inference 沒有產生輸出資料夾。'
    }
    $customCount = (Get-ChildItem -LiteralPath $customDir.FullName -File | Measure-Object).Count
    if ($customCount -lt $sampleCount) {
        throw ("custom inference 輸出張數不足：expected>={0}, actual={1}" -f $sampleCount, $customCount)
    }

    if (-not $SkipTrain) {
        Invoke-LauncherAction -Action 'train-quick'
        $trainDir = Get-LatestChildDirectory -RootPath $TrainRoot
        if (-not $trainDir) {
            throw 'quick train 沒有產生訓練輸出資料夾。'
        }
        $latestCkpt = Join-Path $trainDir.FullName 'weights\latest.pth.tar'
        if (-not (Test-Path -LiteralPath $latestCkpt)) {
            throw ("quick train 缺少 checkpoint：{0}" -f $latestCkpt)
        }
    }

    Write-Host ''
    Write-Host 'SMOKE TEST OK'
    Write-Host ('demo_output={0}' -f $demoDir.FullName)
    Write-Host ('custom_output={0}' -f $customDir.FullName)
    if (-not $SkipTrain) {
        Write-Host ('train_output_root={0}' -f (Join-Path $TrainRoot '_smoketest'))
    }
}
finally {
    Write-Utf8BomFile -Path $ConfigPath -Content $originalConfig
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}


