param(
    [string]$Device = "cuda:0",
    [string]$DemoDevice = "cpu",
    [int]$Epochs = 120,
    [int]$BatchSize = 8,
    [int]$ValBatchSize = 2,
    [int]$NumWorkers = 4,
    [int]$SeqBatchSize = 2,
    [string]$RunName = "",
    [switch]$Scratch,
    [switch]$OpenForegroundMonitor
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($RunName)) {
    $RunName = "full_training_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$RunPrefix = "V42_SoftLabelSNR_$RunName"
$LogRoot = Join-Path $PackageRoot ("results\run_logs\" + $RunName)
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

function Quote-Arg([string]$Value) {
    '"' + ($Value -replace '"', '\"') + '"'
}

$Python = (Get-Command python).Source
$TrainScript = Join-Path $PackageRoot "train_v42.py"
$MonitorScript = Join-Path $PackageRoot "epoch_demo_monitor.py"
$ForegroundMonitorScript = Join-Path $PackageRoot "open_foreground_epoch_monitor.ps1"

$env:PYTHONUNBUFFERED = "1"

$TrainArgs = @(
    (Quote-Arg $TrainScript),
    "--device", (Quote-Arg $Device),
    "--run-name", (Quote-Arg $RunName),
    "--num-epoch", (Quote-Arg ([string]$Epochs)),
    "--batch-size", (Quote-Arg ([string]$BatchSize)),
    "--val-batch-size", (Quote-Arg ([string]$ValBatchSize)),
    "--num-workers", (Quote-Arg ([string]$NumWorkers)),
    "--seq-batch-size", (Quote-Arg ([string]$SeqBatchSize))
)
if ($Scratch) {
    $TrainArgs += "--scratch"
}
$TrainArgLine = $TrainArgs -join " "

$TrainOut = Join-Path $LogRoot "train_stdout.log"
$TrainErr = Join-Path $LogRoot "train_stderr.log"
$TrainProcess = Start-Process `
    -FilePath $Python `
    -ArgumentList $TrainArgLine `
    -WorkingDirectory $PackageRoot `
    -RedirectStandardOutput $TrainOut `
    -RedirectStandardError $TrainErr `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 5

$MonitorArgs = @(
    (Quote-Arg $MonitorScript),
    "--run-prefix", (Quote-Arg $RunPrefix),
    "--device", (Quote-Arg $DemoDevice),
    "--training-pid", (Quote-Arg ([string]$TrainProcess.Id)),
    "--poll-sec", "20",
    "--stable-wait-sec", "2",
    "--idle-exit-sec", "300"
)
$MonitorArgLine = $MonitorArgs -join " "

$MonitorOut = Join-Path $LogRoot "epoch_demo_monitor_stdout.log"
$MonitorErr = Join-Path $LogRoot "epoch_demo_monitor_stderr.log"
$MonitorProcess = Start-Process `
    -FilePath $Python `
    -ArgumentList $MonitorArgLine `
    -WorkingDirectory $PackageRoot `
    -RedirectStandardOutput $MonitorOut `
    -RedirectStandardError $MonitorErr `
    -WindowStyle Hidden `
    -PassThru

$ForegroundProcess = $null

$Manifest = [ordered]@{
    package_root = $PackageRoot
    run_name = $RunName
    run_prefix = $RunPrefix
    epochs = $Epochs
    batch_size = $BatchSize
    val_batch_size = $ValBatchSize
    num_workers = $NumWorkers
    seq_batch_size = $SeqBatchSize
    training_device = $Device
    demo_device = $DemoDevice
    scratch = [bool]$Scratch
    train_pid = $TrainProcess.Id
    monitor_pid = $MonitorProcess.Id
    foreground_monitor_pid = $null
    train_stdout = $TrainOut
    train_stderr = $TrainErr
    monitor_stdout = $MonitorOut
    monitor_stderr = $MonitorErr
    expected_training_folder_prefix = "training_progress_$RunPrefix"
    epoch_demo_output = "inside each training_progress folder: epoch_demo_inference"
    started_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}
$ManifestPath = Join-Path $LogRoot "launch_manifest.json"
$Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $PackageRoot "CURRENT_FULL_TRAINING_RUN.json") -Force

if ($OpenForegroundMonitor) {
    $PwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($null -eq $PwshCmd) {
        $Pwsh = "powershell.exe"
    } else {
        $Pwsh = $PwshCmd.Source
    }
    $ForegroundArgs = @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (Quote-Arg $ForegroundMonitorScript),
        "-PollSec", "5",
        "-BatchSize", (Quote-Arg ([string]$BatchSize))
    ) -join " "
    $ForegroundProcess = Start-Process `
        -FilePath $Pwsh `
        -ArgumentList $ForegroundArgs `
        -WorkingDirectory $PackageRoot `
        -WindowStyle Normal `
        -PassThru
    $Manifest.foreground_monitor_pid = $ForegroundProcess.Id
    $Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
    Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $PackageRoot "CURRENT_FULL_TRAINING_RUN.json") -Force
}

Write-Host "Started V42 full training."
Write-Host "Run name: $RunName"
Write-Host "Training PID: $($TrainProcess.Id)"
Write-Host "Epoch demo monitor PID: $($MonitorProcess.Id)"
if ($ForegroundProcess -ne $null) {
    Write-Host "Foreground epoch monitor PID: $($ForegroundProcess.Id)"
}
Write-Host "Logs: $LogRoot"
Write-Host "Manifest: $ManifestPath"
