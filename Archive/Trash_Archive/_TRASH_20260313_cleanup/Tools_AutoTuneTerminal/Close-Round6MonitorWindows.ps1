param(
    [ValidateSet("all", "status", "output")]
    [string]$Mode = "all"
)

$ErrorActionPreference = "SilentlyContinue"

$toolRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFiles = @()
if ($Mode -in @("all", "status")) {
    $pidFiles += (Join-Path $toolRoot ".round6_status_window.pid")
}
if ($Mode -in @("all", "output")) {
    $pidFiles += (Join-Path $toolRoot ".round6_output_window.pid")
}

foreach ($pidFile in $pidFiles) {
    if (Test-Path $pidFile) {
        $pidText = Get-Content $pidFile | Select-Object -First 1
        if ($pidText) {
            Stop-Process -Id ([int]$pidText) -Force
        }
        Remove-Item $pidFile -Force
    }
}

$watchPatterns = @()
if ($Mode -in @("all", "status")) {
    $watchPatterns += "*WATCH_ROUND6_STATUS.cmd*"
}
if ($Mode -in @("all", "output")) {
    $watchPatterns += "*WATCH_ROUND6_OUTPUT.cmd*"
}

$pyPatterns = @()
if ($Mode -in @("all", "status")) {
    $pyPatterns += "*GeoEdgeAlignSR_v1_Round6StatusWatch.py*"
}
if ($Mode -in @("all", "output")) {
    $pyPatterns += "*GeoEdgeAlignSR_v1_Round6OutputWatch.py*"
}

$matchedProcessIds = [System.Collections.Generic.HashSet[int]]::new()
$relatedParentIds = [System.Collections.Generic.HashSet[int]]::new()

$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @("cmd.exe", "python.exe", "powershell.exe", "pwsh.exe")
}

foreach ($proc in $procs) {
    $cmdLine = [string]$proc.CommandLine
    $matched = $false

    foreach ($pat in $watchPatterns) {
        if ($cmdLine -like $pat) {
            $matched = $true
            break
        }
    }
    if (-not $matched) {
        foreach ($pat in $pyPatterns) {
            if ($cmdLine -like $pat) {
                $matched = $true
                break
            }
        }
    }

    if ($matched) {
        $null = $matchedProcessIds.Add([int]$proc.ProcessId)
        $null = $relatedParentIds.Add([int]$proc.ParentProcessId)
    }
}

foreach ($procId in $matchedProcessIds) {
    Stop-Process -Id $procId -Force
}

$conhosts = Get-CimInstance Win32_Process -Filter "Name='conhost.exe'"
foreach ($proc in $conhosts) {
    if ($matchedProcessIds.Contains([int]$proc.ParentProcessId) -or $relatedParentIds.Contains([int]$proc.ParentProcessId)) {
        Stop-Process -Id $proc.ProcessId -Force
    }
}
