param()

$ErrorActionPreference = "Stop"

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = [System.IO.Path]::GetFullPath((Join-Path $toolRoot ".."))
$pidFile = Join-Path $toolRoot ".output_window.pid"
$statusPath = Join-Path $root "runtime\R32_STATUS.json"

$log = ""
if (Test-Path $statusPath) {
    try {
        $status = Get-Content $statusPath -Raw | ConvertFrom-Json
        $log = [string]$status.active_log
    } catch {
        $log = ""
    }
}
if (-not $log) {
    throw "No active log found in sandbox runtime status."
}

$tailCmd = '$Host.UI.RawUI.WindowTitle = ''Training Output''; Get-Content -Path ''' + $log + ''' -Tail 60 -Wait'
$p = Start-Process powershell.exe -ArgumentList '-NoExit','-NoProfile','-Command', $tailCmd -PassThru
Set-Content $pidFile $p.Id -Encoding ASCII
Write-Output "WATCH_PID=$($p.Id)"
Write-Output "WATCH_LOG=$log"
