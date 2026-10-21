$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
function DurationText($seconds) {
    if ($null -eq $seconds) { return 'estimating' }
    return [TimeSpan]::FromSeconds([Math]::Max(0,[double]$seconds)).ToString('hh\:mm\:ss')
}
while ($true) {
    $active = Get-Content (Join-Path $root 'runs\active_run.json') -Raw | ConvertFrom-Json
    Clear-Host
    Write-Host 'Training monitor' -ForegroundColor Cyan
    if (-not $active) { Write-Host 'No run found.'; break }
    Write-Host $active.run_id
    $state = Get-Content (Join-Path $active.path 'state.json') -Raw | ConvertFrom-Json
    $livePath = Join-Path $active.path 'live.json'
    $live = Get-Content $livePath -Raw | ConvertFrom-Json
    if ($live) {
        Write-Host ('Epoch {0}/{1}   Batch {2}/{3}' -f $live.epoch,$live.epochs,$live.step,$live.steps)
        Write-Host ('Stage: {0}   Loss: {1:N5}' -f $live.stage,$live.loss)
        $age = ((Get-Date) - (Get-Item $livePath).LastWriteTime).TotalSeconds
        Write-Host ('Epoch left: {0}' -f (DurationText ($live.epoch_remaining_seconds - $age))) -ForegroundColor Green
        Write-Host ('Total left: {0}' -f (DurationText ($live.estimated_total_remaining_seconds - $age))) -ForegroundColor Green
        Write-Host ('GPU free: {0:N1} GiB' -f $live.gpu_free_gib)
        if ($age -gt 60) { Write-Host 'Waiting for the next measured update or validation.' -ForegroundColor Yellow }
    }
    if ($state.status -eq 'complete') { Write-Host 'Complete.' -ForegroundColor Green; break }
    if ($state.status -eq 'failed') { Write-Host $state.error -ForegroundColor Red; break }
    Start-Sleep -Seconds 3
}
