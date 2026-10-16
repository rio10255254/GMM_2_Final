$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Progress = Join-Path $Root 'runs\launcher_logs\active_formal_run.json'
Write-Host 'R88 formal training monitor' -ForegroundColor Cyan
while ($true) {
    Clear-Host
    Write-Host 'R88 formal training monitor' -ForegroundColor Cyan
    Write-Host (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    if (Test-Path $Progress) {
        $State = Get-Content -Raw -Path $Progress | ConvertFrom-Json
        Write-Host ("Status: " + $State.status)
        Write-Host ("Epoch: " + $State.completed_epoch + " / " + $State.planned_epochs)
        Write-Host ("Run: " + $State.run_id)
        if ($State.latest_metrics) {
            Write-Host ("Last epoch seconds: " + [math]::Round($State.latest_metrics.seconds, 1))
            Write-Host ("Peak GPU GiB: " + [math]::Round($State.latest_metrics.gpu_peak_gib, 2))
        }
        if ($State.status -in @('complete', 'failed')) { break }
    } else {
        Write-Host 'Waiting for training to start...'
    }
    Start-Sleep -Seconds 5
}
