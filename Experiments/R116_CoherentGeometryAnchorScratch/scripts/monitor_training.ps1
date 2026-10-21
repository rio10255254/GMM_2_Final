$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$lock = Join-Path $root 'runs\active_run.lock'
while ($true) {
    Clear-Host
    Write-Host 'R116 Training Monitor' -ForegroundColor Cyan
    Write-Host (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    if (-not (Test-Path -LiteralPath $lock)) {
        Write-Host 'No active R116 run.' -ForegroundColor Yellow
        break
    }
    $runId = (Get-Content -LiteralPath $lock -Raw).Trim()
    $runDir = Join-Path (Join-Path $root 'runs') $runId
    $livePath = Join-Path $runDir 'live_state.json'
    $statePath = Join-Path $runDir 'run_state.json'
    Write-Host ('Run: ' + $runId)
    if (Test-Path -LiteralPath $livePath) {
        $live = Get-Content -LiteralPath $livePath -Raw | ConvertFrom-Json
        Write-Host ('Epoch {0}/{1}  batch {2}/{3}' -f $live.epoch, $live.epochs, $live.batch, $live.batches)
        Write-Host ('Stage: {0}  active: {1}  paired: {2}' -f $live.stage, $live.active_group, $live.paired)
        Write-Host ('Loss: {0:N6}  gradient: {1:N4}  LR: {2:E2}' -f $live.loss, $live.gradient_norm, $live.learning_rate)
        Write-Host ('GPU free: {0:N2}/{1:N2} GiB' -f $live.gpu_free_gib, $live.gpu_total_gib)
    } elseif (Test-Path -LiteralPath $statePath) {
        Get-Content -LiteralPath $statePath -Raw
    } else {
        Write-Host 'Run is starting; telemetry is not available yet.'
    }
    Start-Sleep -Seconds 3
}
