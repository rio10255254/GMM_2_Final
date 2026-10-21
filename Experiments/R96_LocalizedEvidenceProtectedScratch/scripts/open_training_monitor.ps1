[CmdletBinding()]
param(
    [int]$RefreshSeconds = 3,
    [switch]$ForceNew
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Monitor = Join-Path $Root "scripts\monitor_training.ps1"
$StatePath = Join-Path $Root "logs\monitor_state.json"
$EscapedMonitor = [Regex]::Escape($Monitor)
$Existing = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and
    $_.Name -match "powershell|pwsh" -and
    [string]$_.CommandLine -match $EscapedMonitor
})

if ($Existing.Count -gt 0 -and -not $ForceNew) {
    Write-Host ("R96 monitor is already open. PID: " + ($Existing.ProcessId -join ", ")) -ForegroundColor Yellow
    exit 0
}

$Arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"' + $Monitor + '"'),
    "-RefreshSeconds", [string][Math]::Max(1, $RefreshSeconds)
)
$Process = Start-Process -FilePath "powershell.exe" -ArgumentList $Arguments -WorkingDirectory $Root -PassThru
$State = @{
    process_id = $Process.Id
    monitor = $Monitor
    refresh_seconds = [Math]::Max(1, $RefreshSeconds)
    opened_at = (Get-Date).ToString("o")
}
$State | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8
Write-Host "R96 compact full monitor opened. PID: $($Process.Id)" -ForegroundColor Cyan
