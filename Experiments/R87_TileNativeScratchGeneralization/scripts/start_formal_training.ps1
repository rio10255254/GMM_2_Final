$ErrorActionPreference = "Stop"
$Experiment = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = python
$LogDir = Join-Path $Experiment "results\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$OutLog = Join-Path $LogDir "formal_training.log"
$ErrLog = Join-Path $LogDir "formal_training_error.log"

Write-Host "Starting R87 scratch training" -ForegroundColor Cyan
Write-Host "Experiment: $Experiment"
Write-Host "Output log: $OutLog"

$Process = Start-Process -FilePath $Python `
    -ArgumentList @((Join-Path $Experiment "training\train_r87.py"), "--device", "cuda:0", "--seed", "870031", "--epochs", "100", "--num-workers", "4") `
    -WorkingDirectory $Experiment `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru

$Process.Id | Set-Content -LiteralPath (Join-Path $LogDir "formal_training.pid") -Encoding ASCII
Write-Host "PID: $($Process.Id)" -ForegroundColor Green
Write-Host "Use scripts\monitor_training.ps1 to watch progress."

