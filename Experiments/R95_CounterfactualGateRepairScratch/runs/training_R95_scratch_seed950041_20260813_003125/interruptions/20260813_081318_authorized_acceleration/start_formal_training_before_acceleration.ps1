param(
    [string]$Device = "cuda:0",
    [int]$NumWorkers = 4,
    [switch]$ContinueInterruptedFormal
)
$ErrorActionPreference = "Stop"
$env:CUDA_MODULE_LOADING = "EAGER"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = python
$LogDirectory = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$LogStem = if ($ContinueInterruptedFormal) { "formal_continuation" } else { "formal" }
$Stdout = Join-Path $LogDirectory ($LogStem + "_stdout.log")
$Stderr = Join-Path $LogDirectory ($LogStem + "_stderr.log")
$Arguments = @(
    "-u",
    (Join-Path $Root "scripts\launch_r95.py"),
    "--device", $Device,
    "--num-workers", $NumWorkers
)
if ($ContinueInterruptedFormal) {
    $Arguments += "--continue-interrupted-formal"
}
$Process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru -WindowStyle Hidden
$State = @{
    process_id = $Process.Id
    started_at = (Get-Date).ToString("o")
    stdout = $Stdout
    stderr = $Stderr
    continuation = [bool]$ContinueInterruptedFormal
}
$State | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LogDirectory "launcher_state.json") -Encoding UTF8
Write-Host "R95 formal training started. PID: $($Process.Id)"
Write-Host "Monitor: $Root\scripts\monitor_training.ps1"

