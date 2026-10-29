param(
    [string]$Device = "cuda:0",
    [int]$CpuThreads = 8
)
$ErrorActionPreference = "Stop"
$env:CUDA_MODULE_LOADING = "EAGER"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = python
$LogDirectory = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$LogStem = "formal"
$Stdout = Join-Path $LogDirectory ($LogStem + "_stdout.log")
$Stderr = Join-Path $LogDirectory ($LogStem + "_stderr.log")
$RegistryPath = Join-Path $Root "runs\formal_run_registry.json"
$Continuation = Test-Path -LiteralPath $RegistryPath
if ($Continuation -and ((Test-Path -LiteralPath $Stdout) -or (Test-Path -LiteralPath $Stderr))) {
    $History = Join-Path $LogDirectory "history"
    New-Item -ItemType Directory -Force -Path $History | Out-Null
    $Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    if (Test-Path -LiteralPath $Stdout) {
        Copy-Item -LiteralPath $Stdout -Destination (Join-Path $History ("formal_" + $Stamp + "_stdout.log"))
    }
    if (Test-Path -LiteralPath $Stderr) {
        Copy-Item -LiteralPath $Stderr -Destination (Join-Path $History ("formal_" + $Stamp + "_stderr.log"))
    }
}
$Arguments = @(
    "-u",
    (Join-Path $Root "scripts\launch_r97.py"),
    "--device", $Device,
    "--cpu-threads", $CpuThreads
)
$Process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru -WindowStyle Hidden
$State = @{
    process_id = $Process.Id
    started_at = (Get-Date).ToString("o")
    stdout = $Stdout
    stderr = $Stderr
    continuation = [bool]$Continuation
    cpu_threads = $CpuThreads
}
$State | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LogDirectory "launcher_state.json") -Encoding UTF8
Write-Host "R97 formal training started. PID: $($Process.Id)"
Write-Host "Monitor: $Root\scripts\monitor_training.ps1"


