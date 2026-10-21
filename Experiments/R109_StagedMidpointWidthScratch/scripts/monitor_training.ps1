param([int]$RefreshSeconds = 5)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$lock = Join-Path $root 'runs\active_run.lock'

while ($true) {
    Clear-Host
    Write-Host 'R109 Training Monitor' -ForegroundColor Cyan
    Write-Host (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    if (-not (Test-Path -LiteralPath $lock)) {
        Write-Host 'No active run.' -ForegroundColor Yellow
        Start-Sleep -Seconds $RefreshSeconds
        continue
    }
    $runId = (Get-Content -LiteralPath $lock -Raw).Trim()
    $run = Join-Path $root "runs\$runId"
    $statePath = Join-Path $run 'run_state.json'
    $historyPath = Join-Path $run 'training_history.json'
    Write-Host "Run: $runId"
    if (Test-Path -LiteralPath $statePath) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        Write-Host "Status: $($state.status)  Device: $($state.device)"
    }
    if (Test-Path -LiteralPath $historyPath) {
        $parsed = Get-Content -LiteralPath $historyPath -Raw | ConvertFrom-Json
        $history = @()
        foreach ($entry in $parsed) {
            if ($null -ne $entry.duration_seconds) { $history += $entry }
        }
        if ($history.Count -gt 0) {
            $last = $history[$history.Count - 1]
            $take = [Math]::Min(5, $history.Count)
            $recent = @($history | Select-Object -Last $take)
            $durations = @($recent | ForEach-Object { [double]$_.duration_seconds })
            $seconds = ($durations | Measure-Object -Average).Average
            $remaining = [Math]::Max(0, 48 - [int]$last.epoch)
            $eta = [TimeSpan]::FromSeconds([double]$seconds * $remaining)
            Write-Host "Epoch: $($last.epoch)/48  Stage: $($last.stage)" -ForegroundColor Green
            Write-Host ("Last epoch: {0:N1}s  Dynamic remaining: {1:hh\:mm\:ss}" -f [double]$last.duration_seconds, $eta)
            Write-Host ("Train loss: {0:N6}" -f [double]$last.train_total)
            Write-Host ("Boundary localization: {0:N6}" -f [double]$last.validation_detector_boundary_dice)
            Write-Host 'Mode: continuous width and normal shift; no binary need gate.' -ForegroundColor DarkCyan
            Write-Host ("Contour: {0:N6}  Identity change: {1:N6}" -f [double]$last.validation_renderer_contour, [double]$last.validation_renderer_identity)
            Write-Host ("Width gain: {0:N4}  Normal shift: {1:N4}px" -f [double]$last.validation_width_gain_mean, [double]$last.validation_normal_shift_abs_mean)
            Write-Host ("GPU peak reserved: {0:N2} GiB" -f [double]$last.gpu_peak_reserved_gib)
        }
    }
    Start-Sleep -Seconds $RefreshSeconds
}
