param(
    [switch]$NoMonitor
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = python
$Entry = Join-Path $Root "training\run_recovery_training.py"
$Source = Join-Path $Root "weights\formal\seed_1000053\R100_scratch_seed1000053_20260814_180143\weights\epoch_036.pth.tar"
$Registry = Join-Path $Root "runs\formal_run_registry.json"
$LauncherState = Join-Path $Root "logs\launcher_state.json"
$Stdout = Join-Path $Root "logs\recovery_stdout.log"
$Stderr = Join-Path $Root "logs\recovery_stderr.log"

if (-not (Test-Path -LiteralPath $Python)) { throw "Python was not found: $Python" }
if (-not (Test-Path -LiteralPath $Entry)) { throw "Recovery entry was not found: $Entry" }
if (-not (Test-Path -LiteralPath $Source)) { throw "The exact E36 recovery source is missing: $Source" }

$Existing = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -match "R100_CausalOperatorScratch" -and
    ($_.CommandLine -match "run_full_training.py" -or $_.CommandLine -match "run_recovery_training.py")
})
if ($Existing.Count -gt 0) { throw "An R100 trainer is already running (PID $($Existing.ProcessId -join ', '))." }

$RegistryObject = Get-Content -Raw -LiteralPath $Registry | ConvertFrom-Json
$Formal = @($RegistryObject.formal_runs)
if ($Formal.Count -ne 1 -or $Formal[0].run_id -ne "R100_scratch_seed1000053_20260814_180143" -or [int]$Formal[0].completed_epoch -ne 36) {
    throw "Recovery requires the single registered R100 run to end exactly at E36."
}

$Start = Get-Date
$Process = Start-Process -FilePath $Python `
    -ArgumentList @($Entry, "--device", "cuda:0", "--num-workers", "4", "--cpu-threads", "8") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr `
    -WindowStyle Hidden `
    -PassThru

[ordered]@{
    experiment_id = "R100_CausalOperatorScratch"
    status = "recovery_launched"
    trainer_pid = $Process.Id
    launched_at = $Start.ToString("o")
    recovery_source_epoch = 36
    stdout = $Stdout
    stderr = $Stderr
    monitor_requested = (-not $NoMonitor)
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $LauncherState -Encoding utf8

Start-Sleep -Seconds 4
if ($Process.HasExited) {
    $Tail = if (Test-Path -LiteralPath $Stderr) { (Get-Content -LiteralPath $Stderr -Tail 30) -join [Environment]::NewLine } else { "No stderr was written." }
    throw "R100 recovery exited during startup.`n$Tail"
}

if (-not $NoMonitor) {
    $Monitor = Join-Path $Root "scripts\monitor_training.ps1"
    $ExistingMonitor = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "powershell.exe" -and $_.CommandLine -match [regex]::Escape($Monitor)
    })
    if ($ExistingMonitor.Count -eq 0) {
        Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Monitor) -WorkingDirectory $Root -WindowStyle Normal | Out-Null
    }
}

Write-Host "R100 recovery E37-E40 started. PID: $($Process.Id)" -ForegroundColor Cyan
