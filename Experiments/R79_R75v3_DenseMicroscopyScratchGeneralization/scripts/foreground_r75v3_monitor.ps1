param(
    [int]$RefreshSeconds = 5,
    [switch]$Once
)

$ErrorActionPreference = "Continue"
$StatusScript = Join-Path $PSScriptRoot "check_r75v3_status.ps1"
$Host.UI.RawUI.WindowTitle = "R75-v3 Training Monitor (Ctrl+C to stop)"

while ($true) {
    Clear-Host
    Write-Host "R75-v3 Formal Training Monitor" -ForegroundColor Cyan
    Write-Host "Refresh interval: $RefreshSeconds seconds. Press Ctrl+C to stop monitoring." -ForegroundColor DarkGray
    Write-Host ""

    try {
        $StatusText = (& $StatusScript | Out-String)
        $Status = $StatusText | ConvertFrom-Json
        $StatusColor = if ($Status.status -eq "running") { "Green" } elseif ($Status.status -eq "complete") { "Cyan" } else { "Yellow" }

        Write-Host ("Status: " + $Status.status) -ForegroundColor $StatusColor
        Write-Host ("Process ID: " + $Status.process_id)
        Write-Host ("Started: " + $Status.started_at)
        Write-Host ("Progress: " + $(if ($Status.last_epoch_line) { $Status.last_epoch_line } else { "waiting for first epoch" })) -ForegroundColor White
        Write-Host ("Live reconstruction images: " + $Status.live_validation_file_count) -ForegroundColor Magenta
        if ($Status.live_validation_counts) {
            Write-Host ("  5x / 20x / 50x: " + $Status.live_validation_counts.five_x + " / " + $Status.live_validation_counts.twenty_x + " / " + $Status.live_validation_counts.fifty_x) -ForegroundColor Magenta
        }
        if ($Status.latest_live_validation_file) {
            Write-Host ("Latest image: " + [string]$Status.latest_live_validation_file) -ForegroundColor Magenta
        }

        if ($Status.status -eq "stopped_or_failed" -and $Status.stderr_tail) {
            Write-Host "" 
            Write-Host "Last error lines:" -ForegroundColor Red
            @($Status.stderr_tail | Select-Object -Last 3) | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        }
    }
    catch {
        Write-Host ("Monitor read error: " + $_.Exception.Message) -ForegroundColor Red
    }

    Write-Host ""
    Write-Host ("Last update: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor DarkGray
    if ($Once) {
        break
    }
    Start-Sleep -Seconds $RefreshSeconds
}
