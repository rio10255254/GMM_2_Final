$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$active = Join-Path $root 'runs\active_run.json'
$registry = Join-Path $root 'runs\formal_run_registry.json'
while ($true) {
    Clear-Host
    Write-Host 'R117 Training Monitor' -ForegroundColor Cyan
    Write-Host (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -ForegroundColor DarkGray
    $runId = $null
    if (Test-Path -LiteralPath $active) { $state = Get-Content $active -Raw | ConvertFrom-Json; $runId = $state.run_id }
    if (-not $runId -and (Test-Path -LiteralPath $registry)) { $reg = Get-Content $registry -Raw | ConvertFrom-Json; $runId = $reg.formal_run_id }
    if (-not $runId) { Write-Host 'No R117 run found.' -ForegroundColor Yellow; break }
    $runDir = Join-Path (Join-Path $root 'runs') $runId
    $statePath = Join-Path $runDir 'run_state.json'
    $livePath = Join-Path $runDir 'live_state.json'
    $logPath = Join-Path $runDir 'training_log.csv'
    Write-Host ('Run    ' + $runId)
    if (Test-Path -LiteralPath $livePath) {
        $live = Get-Content $livePath -Raw | ConvertFrom-Json
        Write-Host ('Epoch  {0}/{1}   Batch {2}/{3}' -f $live.epoch,$live.epochs,$live.batch,$live.batches) -ForegroundColor White
        Write-Host ('Stage  {0}   Group {1}' -f $live.stage,$live.group)
        Write-Host ('Loss   {0:N6}   Grad {1:N4}   LR {2:E2}' -f $live.loss,$live.gradient_norm,$live.learning_rate)
        Write-Host ('GPU    {0:N1} GiB free of {1:N1} GiB' -f $live.gpu_free_gib,$live.gpu_total_gib)
    }
    if (Test-Path -LiteralPath $logPath) {
        $rows = @(Import-Csv -LiteralPath $logPath)
        if ($rows.Count -gt 0) {
            $last = $rows[-1]
            $elapsed = ($rows | Measure-Object -Property duration_seconds -Sum).Sum
            $remaining = [double]$last.estimated_remaining_seconds
            if ($remaining -gt 0) {
                $finish = (Get-Date).AddSeconds($remaining)
                Write-Host ('ETA    {0} remaining   Finish about {1}' -f ([TimeSpan]::FromSeconds($remaining).ToString('hh\:mm\:ss')),$finish.ToString('MM-dd HH:mm')) -ForegroundColor Green
            }
            Write-Host ('Last   contour {0:N4}   detail {1:N4}   identity {2:N5}' -f [double]$last.validation_mean_contour_gain,[double]$last.validation_mean_gradient_gain,[double]$last.validation_identity_change)
        }
    }
    if (Test-Path -LiteralPath $statePath) {
        $runState = Get-Content $statePath -Raw | ConvertFrom-Json
        if ($runState.status -eq 'complete') { Write-Host 'Training complete.' -ForegroundColor Green; break }
        if ($runState.status -eq 'failed') { Write-Host ('Training failed: ' + $runState.error) -ForegroundColor Red; break }
    }
    Start-Sleep -Seconds 3
}
