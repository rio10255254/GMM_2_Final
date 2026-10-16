param(
    [string]$Device = "cuda:0",
    [int]$NumWorkers = 4
)
$ErrorActionPreference = "Stop"
$env:CUDA_MODULE_LOADING = "EAGER"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "C:\Users\Rio\anaconda3\python.exe"
$LogDirectory = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$Stdout = Join-Path $LogDirectory "formal_stdout.log"
$Stderr = Join-Path $LogDirectory "formal_stderr.log"
$Arguments = @(
    "-u",
    (Join-Path $Root "scripts\launch_r94.py"),
    "--device", $Device,
    "--num-workers", $NumWorkers
)
$Process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru -WindowStyle Hidden
$State = @{
    process_id = $Process.Id
    started_at = (Get-Date).ToString("o")
    stdout = $Stdout
    stderr = $Stderr
}
$State | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LogDirectory "launcher_state.json") -Encoding UTF8
Write-Host "R94 formal training started. PID: $($Process.Id)"
Write-Host "Monitor: $Root\scripts\monitor_training.ps1"
