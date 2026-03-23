param()

$cmdWatchers = Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
    Where-Object { $_.CommandLine -like '*WATCH_BACKGROUND_RUN.cmd*' }

$pyWatchers = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*GeoEdgeAlignSR_v1_BackgroundRunWatch.py*' }

$allIds = @()
if ($cmdWatchers) { $allIds += $cmdWatchers.ProcessId }
if ($pyWatchers) { $allIds += $pyWatchers.ProcessId }
$allIds = $allIds | Sort-Object -Unique

foreach ($procId in $allIds) {
    try {
        cmd /c "taskkill /PID $procId /T /F" | Out-Null
    } catch {
    }
}

if ($allIds.Count -gt 0) {
    Write-Output ("Cleaned background watcher ids: " + ($allIds -join ","))
} else {
    Write-Output "Cleaned background watcher ids: none"
}
