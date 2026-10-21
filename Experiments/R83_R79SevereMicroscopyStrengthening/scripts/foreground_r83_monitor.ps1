param([int]$RefreshSeconds = 8)

$ErrorActionPreference = 'Continue'
$StatusScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'check_r83_status.ps1'
Write-Host "R83 foreground monitor. Press Ctrl+C to stop monitoring; training continues." -ForegroundColor Cyan
while ($true) {
    Clear-Host
    Write-Host "R83 monitor  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    & $StatusScript
    Start-Sleep -Seconds ([Math]::Max(2, $RefreshSeconds))
}
