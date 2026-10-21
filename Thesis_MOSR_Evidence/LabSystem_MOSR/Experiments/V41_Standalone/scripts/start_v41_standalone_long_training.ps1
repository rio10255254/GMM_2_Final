param(
    [int]$Epochs = 16,
    [string]$Device = "cuda:0",
    [int]$BatchSize = 4,
    [int]$ValBatchSize = 2,
    [int]$NumWorkers = 2,
    [int]$MaxTrainBatches = 0,
    [string]$RunSuffix = "",
    [switch]$Scratch
)

$ErrorActionPreference = "Stop"

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentDir = Split-Path -Parent $ScriptPath
$ProjectRoot = (Resolve-Path (Join-Path $ExperimentDir "..\..\..")).Path
$Launcher = Join-Path $ScriptPath "launch_v41_standalone.py"
$LogRoot = Join-Path $ExperimentDir "logs"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

if ([string]::IsNullOrWhiteSpace($RunSuffix)) {
    $RunSuffix = "standalone_full_e$($Epochs)_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Stdout = Join-Path $LogRoot "v41_standalone_$($Stamp)_stdout.log"
$Stderr = Join-Path $LogRoot "v41_standalone_$($Stamp)_stderr.log"
$CommandRecord = Join-Path $LogRoot "v41_standalone_$($Stamp)_command.txt"
$PidRecord = Join-Path $LogRoot "v41_standalone_$($Stamp)_process.json"

$ArgsList = @(
    "-X", "utf8",
    $Launcher,
    "--num-epoch", "$Epochs",
    "--device", "$Device",
    "--batch-size", "$BatchSize",
    "--val-batch-size", "$ValBatchSize",
    "--num-workers", "$NumWorkers",
    "--run-suffix", "$RunSuffix"
)

if ($Scratch) {
    $ArgsList += "--scratch"
}

if ($MaxTrainBatches -gt 0) {
    $ArgsList += @("--max-train-batches", "$MaxTrainBatches")
}

Set-Content -LiteralPath $CommandRecord -Encoding UTF8 -Value ("python " + ($ArgsList -join " "))

$env:PYTHONUTF8 = "1"
$Process = Start-Process `
    -FilePath "python" `
    -ArgumentList $ArgsList `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr `
    -WindowStyle Hidden `
    -PassThru

$Info = [ordered]@{
    pid = $Process.Id
    started_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    project_root = $ProjectRoot
    launcher = $Launcher
    epochs = $Epochs
    device = $Device
    batch_size = $BatchSize
    val_batch_size = $ValBatchSize
    num_workers = $NumWorkers
    max_train_batches = $MaxTrainBatches
    run_suffix = $RunSuffix
    stdout = $Stdout
    stderr = $Stderr
    command_record = $CommandRecord
}

$Info | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $PidRecord -Encoding UTF8
$Info | ConvertTo-Json -Depth 3
