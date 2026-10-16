param([string]$RunId = "r115_formal_scratch_20260831")
$root = Split-Path $PSScriptRoot -Parent
$run = Join-Path (Join-Path $root "runs") $RunId
while ($true) {
    Clear-Host
    Write-Host "R115 Training Monitor" -ForegroundColor Cyan
    Write-Host (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    if (Test-Path (Join-Path $run "run_state.json")) {
        $state = Get-Content (Join-Path $run "run_state.json") -Raw | ConvertFrom-Json
        Write-Host ("Run: " + $state.run_id + "  Status: " + $state.status)
    }
    if (Test-Path (Join-Path $run "training_history.json")) {
        $history = Get-Content (Join-Path $run "training_history.json") -Raw | ConvertFrom-Json
        $last = $history[-1]
        Write-Host ("Epoch: " + $last.epoch + "  Stage: " + $last.stage + "  Data: " + $last.data_arm)
        Write-Host ("Common gain: " + ('{0:F6}' -f $last.validation_common_gain_gray) + " gray")
        Write-Host ("Supplemental gain: " + ('{0:F6}' -f $last.validation_supplemental_gain_gray) + " gray")
        Write-Host ("Clear change: " + ('{0:F6}' -f $last.validation_clear_delta_gray) + " gray")
        Write-Host ("GPU peak allocated: " + ('{0:F2}' -f $last.gpu_peak_allocated_gib) + " GiB")
    }
    Start-Sleep -Seconds 5
}

