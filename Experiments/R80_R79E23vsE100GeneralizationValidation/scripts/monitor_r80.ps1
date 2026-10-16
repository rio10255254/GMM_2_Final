$ErrorActionPreference = "Stop"
$ExperimentRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StatusPath = Join-Path $ExperimentRoot "results\run_status.json"
$LogPath = Join-Path $ExperimentRoot "results\logs\r80_full_run.out.log"

Clear-Host
Write-Host "R80 epoch 23 versus epoch 100 validation" -ForegroundColor Cyan
Write-Host ""
if (Test-Path -LiteralPath $StatusPath) {
    $Status = Get-Content -LiteralPath $StatusPath -Raw | ConvertFrom-Json
    Write-Host ("Stage:  " + $Status.current_stage)
    Write-Host ("State:  " + $Status.state)
    Write-Host ("Update: " + $Status.updated_at)
    if ($Status.detail) { Write-Host ("Detail: " + $Status.detail) }
} else {
    Write-Host "Status file has not been created yet."
}
Write-Host ""
if (Test-Path -LiteralPath $LogPath) {
    Get-Content -LiteralPath $LogPath -Tail 25
}
