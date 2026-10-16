param([switch]$NoMonitor)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Entry = Join-Path $Root "training\run_full_training.py"
$Registry = Join-Path $Root "runs\formal_run_registry.json"
$Stdout = Join-Path $Root "logs\formal_stdout.log"
$Stderr = Join-Path $Root "logs\formal_stderr.log"
$LauncherState = Join-Path $Root "logs\launcher_state.json"
$RequiredReports = @(
    (Join-Path $Root "reports\design_preflight.json"),
    (Join-Path $Root "reports\micro_overfit.json"),
    (Join-Path $Root "reports\batch_autotune.json"),
    (Join-Path $Root "reports\formal_runtime_preflight.json")
)

New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs"), (Join-Path $Root "runs") | Out-Null
if (-not (Test-Path -LiteralPath $Python)) { throw "Python was not found." }
if (-not (Test-Path -LiteralPath $Entry)) { throw "The formal training entry was not found." }
foreach ($ReportPath in $RequiredReports) {
    if (-not (Test-Path -LiteralPath $ReportPath)) { throw "Required preflight is missing: $ReportPath" }
    $Report = Get-Content -Raw -LiteralPath $ReportPath | ConvertFrom-Json
    if (($Report.status -ne "passed") -and (-not $Report.passed)) { throw "Required preflight failed: $ReportPath" }
}

$Existing = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -match "R104_PhotometricInvariantCausalGateScratch" -and
    ($_.CommandLine -match "run_full_training.py" -or $_.CommandLine -match "train_r104.py")
})
if ($Existing.Count -gt 0) { throw "R104 training is already running." }
if (Test-Path -LiteralPath $Registry) {
    $RegistryObject = Get-Content -Raw -LiteralPath $Registry | ConvertFrom-Json
    if (@($RegistryObject.formal_runs).Count -gt 0) { throw "The unique formal R104 run is already registered." }
}

$Started = Get-Date
$Process = Start-Process -FilePath $Python -ArgumentList @($Entry) -WorkingDirectory $Root `
    -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -WindowStyle Hidden -PassThru
$State = [ordered]@{
    experiment_id = "R104_PhotometricInvariantCausalGateScratch"
    status = "launched"
    trainer_pid = $Process.Id
    launched_at = $Started.ToString("o")
    stdout = $Stdout
    stderr = $Stderr
    monitor_requested = (-not $NoMonitor)
}
$State | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $LauncherState -Encoding utf8
Start-Sleep -Seconds 5
if ($Process.HasExited) {
    $Tail = if (Test-Path -LiteralPath $Stderr) { (Get-Content -LiteralPath $Stderr -Tail 40) -join [Environment]::NewLine } else { "No error log was written." }
    throw "R104 exited during startup.`n$Tail"
}
if (-not $NoMonitor) {
    $Monitor = Join-Path $Root "scripts\monitor_training.ps1"
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Monitor) -WorkingDirectory $Root -WindowStyle Normal | Out-Null
}
Write-Host "R104 formal scratch training started. PID: $($Process.Id)" -ForegroundColor Cyan
