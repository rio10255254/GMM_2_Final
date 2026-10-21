$ExperimentRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$LogDir = Join-Path $ExperimentRoot 'results\logs'
$PidPath = Join-Path $LogDir 'r83_training.pid'
$RunRoot = Join-Path $ExperimentRoot 'runs'

$PidValue = $null
if (Test-Path -LiteralPath $PidPath) { $PidValue = (Get-Content -LiteralPath $PidPath -Raw).Trim() }
$Running = $false
if ($PidValue) { $Running = $null -ne (Get-Process -Id ([int]$PidValue) -ErrorAction SilentlyContinue) }
Write-Host "R83 running: $Running  PID: $PidValue" -ForegroundColor Cyan

$LatestRun = Get-ChildItem -LiteralPath $RunRoot -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($LatestRun) {
    Write-Host "Latest run: $($LatestRun.FullName)" -ForegroundColor Yellow
    $Progress = Get-ChildItem -LiteralPath $LatestRun.FullName -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'csv|json|log' } | Sort-Object LastWriteTime -Descending | Select-Object -First 8
    $Progress | Format-Table LastWriteTime, Length, FullName -AutoSize
}

$LogPath = Join-Path $LogDir 'r83_training.log'
if (Test-Path -LiteralPath $LogPath) {
    Write-Host "Recent output:" -ForegroundColor Green
    Get-Content -LiteralPath $LogPath -Tail 25
}
$ErrorPath = Join-Path $LogDir 'r83_training_error.log'
if ((Test-Path -LiteralPath $ErrorPath) -and (Get-Item -LiteralPath $ErrorPath).Length -gt 0) {
    Write-Host "Recent errors:" -ForegroundColor Red
    Get-Content -LiteralPath $ErrorPath -Tail 25
}
