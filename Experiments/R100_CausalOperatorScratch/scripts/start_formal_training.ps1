param(
    [switch]$NoMonitor
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Entry = Join-Path $Root "training\run_full_training.py"
$Logs = Join-Path $Root "logs"
$Runs = Join-Path $Root "runs"
$Stdout = Join-Path $Logs "formal_stdout.log"
$Stderr = Join-Path $Logs "formal_stderr.log"
$LauncherState = Join-Path $Logs "launcher_state.json"
$Registry = Join-Path $Runs "formal_run_registry.json"

New-Item -ItemType Directory -Force -Path $Logs, $Runs | Out-Null

$Existing = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and
    $_.CommandLine -match "R100_CausalOperatorScratch" -and
    ($_.CommandLine -match "run_full_training.py" -or
     ($_.CommandLine -match "train_r100.py" -and $_.CommandLine -match "--run-kind\s+formal"))
})
if ($Existing.Count -gt 0) {
    throw "The formal R100 trainer is already running (PID $($Existing.ProcessId -join ', '))."
}

if (Test-Path -LiteralPath $Registry) {
    $RegistryObject = Get-Content -Raw -LiteralPath $Registry | ConvertFrom-Json
    if (@($RegistryObject.formal_runs).Count -gt 0) {
        throw "The single formal R100 run is already registered. A second run is not allowed."
    }
}

if (-not (Test-Path -LiteralPath $Python)) { throw "Python was not found: $Python" }
if (-not (Test-Path -LiteralPath $Entry)) { throw "Training entry was not found: $Entry" }

$Start = Get-Date
$Process = Start-Process -FilePath $Python `
    -ArgumentList @($Entry, "--device", "cuda:0", "--num-workers", "4", "--cpu-threads", "8") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr `
    -WindowStyle Hidden `
    -PassThru

$State = [ordered]@{
    experiment_id = "R100_CausalOperatorScratch"
    status = "launched"
    trainer_pid = $Process.Id
    launched_at = $Start.ToString("o")
    stdout = $Stdout
    stderr = $Stderr
    monitor_requested = (-not $NoMonitor)
}
$State | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $LauncherState -Encoding utf8

Start-Sleep -Seconds 3
if ($Process.HasExited) {
    $Tail = if (Test-Path -LiteralPath $Stderr) { (Get-Content -LiteralPath $Stderr -Tail 20) -join [Environment]::NewLine } else { "No stderr was written." }
    throw "R100 exited during startup.`n$Tail"
}

if (-not $NoMonitor) {
    $Monitor = Join-Path $Root "scripts\monitor_training.ps1"
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Monitor) -WorkingDirectory $Root -WindowStyle Normal | Out-Null
}

Write-Host "R100 formal scratch training started. PID: $($Process.Id)" -ForegroundColor Cyan
Write-Host "The monitor reads the committed epoch log; closing it does not stop training." -ForegroundColor DarkGray
