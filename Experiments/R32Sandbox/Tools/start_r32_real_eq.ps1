param(
    [string]$PythonExe = "C:\Users\Rio\anaconda3\python.exe",
    [string]$CandidateFilter = "r32_real_eq_finetune",
    [double]$ExpectDy = 0.8,
    [int]$SweepEpochs = 40,
    [int]$FinalEpochs = 20,
    [int]$Seed = 1261830
)

$ErrorActionPreference = "Stop"

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sandboxRoot = [System.IO.Path]::GetFullPath((Join-Path $toolRoot ".."))
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $toolRoot "..\..\.."))
$logRoot = Join-Path $sandboxRoot "runtime\logs"
$statusJson = Join-Path $sandboxRoot "runtime\R32_STATUS.json"
$statusMd = Join-Path $sandboxRoot "runtime\R32_STATUS.md"
$waitScript = Join-Path $toolRoot "WAIT_R32_REAL_EQ.ps1"

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$stdout = Join-Path $logRoot "round32_real_eq_rerun_${ts}.log"
$stderr = Join-Path $logRoot "round32_real_eq_rerun_${ts}.log.err"

$argList = @(
    "-u",
    "Experiments\R32Sandbox\Model\autotune_r32.py",
    "--profile", "round32_domain_capacity_probe",
    "--candidate-filter", $CandidateFilter,
    "--expect-dy", "$ExpectDy",
    "--sweep-epochs", "$SweepEpochs",
    "--final-epochs", "$FinalEpochs",
    "--seed", "$Seed",
    "--deterministic",
    "--skip-final"
)

$p = Start-Process -FilePath $PythonExe -ArgumentList $argList -WorkingDirectory $projectRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$launchedAt = [DateTimeOffset]::Now.ToUnixTimeSeconds()

$payload = [ordered]@{
    state = "running"
    step_index = 1
    active_label = "round32_real_eq_rerun"
    active_command = ($PythonExe + " " + ($argList -join " "))
    plan_done = 0
    plan_total = 5
    last_report = ""
    last_exit = ""
    selected_candidate = ""
    selected_checkpoint = ""
    active_pid = $p.Id
    active_log = $stdout
    active_err_log = $stderr
    note = "launched through sandbox START_R32_REAL_EQ.ps1"
    updated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
}

$payload | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $statusJson
@(
    "state: $($payload.state)"
    "step_index: $($payload.step_index)"
    "active_label: $($payload.active_label)"
    "active_command: $($payload.active_command)"
    "plan_done: $($payload.plan_done)"
    "plan_total: $($payload.plan_total)"
    "last_report: $($payload.last_report)"
    "last_exit: $($payload.last_exit)"
    "selected_candidate: $($payload.selected_candidate)"
    "selected_checkpoint: $($payload.selected_checkpoint)"
    "active_pid: $($payload.active_pid)"
    "active_log: $($payload.active_log)"
    "active_err_log: $($payload.active_err_log)"
    "note: $($payload.note)"
    "updated_at: $($payload.updated_at)"
) | Set-Content -Encoding utf8 $statusMd

Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $waitScript,
    "-PidToWatch", "$($p.Id)",
    "-Profile", "round32_domain_capacity_probe",
    "-LaunchedAt", "$launchedAt",
    "-StdoutPath", $stdout,
    "-StderrPath", $stderr
) | Out-Null

Write-Output "PID=$($p.Id)"
Write-Output "ACTIVE_LOG=$stdout"
Write-Output "ACTIVE_ERR_LOG=$stderr"
