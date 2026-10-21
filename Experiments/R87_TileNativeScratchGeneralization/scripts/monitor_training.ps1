$ErrorActionPreference = "Stop"
$Experiment = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Active = Join-Path $Experiment "runs\launcher_logs\active_formal_run.json"
$OutLog = Join-Path $Experiment "results\logs\formal_training.log"
$ErrLog = Join-Path $Experiment "results\logs\formal_training_error.log"

Clear-Host
Write-Host "R87 scratch training monitor" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to close the monitor. Training will continue."

while ($true) {
    Write-Host ""
    Write-Host (Get-Date -Format "yyyy-MM-dd HH:mm:ss") -ForegroundColor DarkGray
    if (Test-Path -LiteralPath $Active) {
        $State = Get-Content -LiteralPath $Active -Raw | ConvertFrom-Json
        Write-Host "Status: $($State.status)"
        Write-Host "Epoch: $($State.completed_epoch) / $($State.planned_epochs)"
        Write-Host "Best epoch: $($State.best_epoch)"
        Write-Host "Best validation: $($State.best_validation_total)"
    } else {
        Write-Host "Waiting for active run marker..." -ForegroundColor Yellow
    }
    if (Test-Path -LiteralPath $OutLog) {
        Write-Host "Recent output:" -ForegroundColor Green
        Get-Content -LiteralPath $OutLog -Tail 3
    }
    if ((Test-Path -LiteralPath $ErrLog) -and ((Get-Item -LiteralPath $ErrLog).Length -gt 0)) {
        Write-Host "Recent errors:" -ForegroundColor Red
        Get-Content -LiteralPath $ErrLog -Tail 8
    }
    Start-Sleep -Seconds 10
}

