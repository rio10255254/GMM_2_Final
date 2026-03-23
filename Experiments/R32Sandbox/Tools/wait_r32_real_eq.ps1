param(
    [int]$PidToWatch,
    [string]$Profile = "round32_domain_capacity_probe",
    [long]$LaunchedAt = 0,
    [string]$StdoutPath = "",
    [string]$StderrPath = ""
)

$ErrorActionPreference = "SilentlyContinue"

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$sandboxRoot = [System.IO.Path]::GetFullPath((Join-Path $toolRoot ".."))
$statusJson = Join-Path $sandboxRoot "runtime\R32_STATUS.json"
$statusMd = Join-Path $sandboxRoot "runtime\R32_STATUS.md"
$reportRoot = Join-Path $sandboxRoot "reports"

try {
    Wait-Process -Id $PidToWatch
} catch {
}

$reportPath = ""
$reportStatus = ""
$cutoff = [DateTimeOffset]::FromUnixTimeSeconds([Math]::Max(0, $LaunchedAt)).LocalDateTime

$reports = Get-ChildItem $reportRoot -Filter "auto_tune_report_*.json" | Sort-Object LastWriteTime -Descending
foreach ($path in $reports) {
    if ($path.LastWriteTime -lt $cutoff) { continue }
    try {
        $payload = Get-Content $path.FullName -Raw | ConvertFrom-Json
    } catch {
        continue
    }
    if (($payload.profile | Out-String).Trim() -ne $Profile) { continue }
    $reportPath = $path.FullName
    $reportStatus = (($payload.status | Out-String).Trim())
    break
}

$state = "error"
$lastExit = "1"
$note = "R32 child process exited without a new report."
if ($reportPath) {
    if ($reportStatus -eq "ok") {
        $state = "completed"
        $lastExit = "0"
        $note = "R32 child process completed and wrote a successful report."
    } else {
        $state = "error"
        $lastExit = "1"
        $note = "R32 child process exited; latest report status=$reportStatus."
    }
}

$payload = [ordered]@{
    state = $state
    step_index = 1
    active_label = "round32_real_eq_rerun"
    active_command = ""
    plan_done = 0
    plan_total = 5
    last_report = $reportPath
    last_exit = $lastExit
    selected_candidate = ""
    selected_checkpoint = ""
    active_pid = 0
    active_log = $StdoutPath
    active_err_log = $StderrPath
    note = $note
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
