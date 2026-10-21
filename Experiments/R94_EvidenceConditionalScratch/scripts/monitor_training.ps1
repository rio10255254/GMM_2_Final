param([int]$RefreshSeconds = 3)
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Progress = Join-Path $Root "runs\active_run.json"
$Registry = Join-Path $Root "runs\formal_run_registry.json"
$Log = Join-Path $Root "logs\formal_stdout.log"
while ($true) {
    Clear-Host
    Write-Host "R94 Training Monitor" -ForegroundColor Cyan
    Write-Host (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    if (Test-Path -LiteralPath $Progress) {
        try {
            $State = Get-Content -Raw -LiteralPath $Progress | ConvertFrom-Json
            Write-Host "Status: $($State.status)"
            Write-Host "Epoch: $($State.completed_epoch) / $($State.planned_epochs)"
            if ($State.latest_metrics) {
                $M = $State.latest_metrics
                Write-Host ("Phase: {0}" -f $M.phase.name)
                Write-Host ("Last epoch: {0:N1} min" -f ($M.seconds / 60.0))
                Write-Host ("GPU peak: {0:N2} GiB | estimated free: {1:N2} GiB" -f $M.gpu_peak_gib, $M.gpu_estimated_free_gib)
                if ($M.validation) {
                    Write-Host ("Detail {0:N4} | Contour {1:N4} | Identity {2:N3} gray | Motion {3:N4}" -f $M.validation.detail_axis, $M.validation.contour_axis, $M.validation.identity_axis, $M.validation.motion_axis)
                }
                if ($State.completed_epoch -gt 0) {
                    $Remaining = [Math]::Max(0, $State.planned_epochs - $State.completed_epoch)
                    Write-Host ("Approx. remaining: {0:N1} hours" -f ($Remaining * $M.seconds / 3600.0))
                }
            }
            if ($State.real_preview_paths) {
                Write-Host "Latest real previews:"
                $State.real_preview_paths | ForEach-Object { Write-Host "  $_" }
            }
        } catch {
            Write-Host "Progress file is being updated..." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Waiting for the first completed epoch..." -ForegroundColor Yellow
    }
    if (Test-Path -LiteralPath $Log) {
        Write-Host ""
        Write-Host "Latest output:" -ForegroundColor DarkCyan
        Get-Content -LiteralPath $Log -Tail 4
    }
    Start-Sleep -Seconds $RefreshSeconds
}
