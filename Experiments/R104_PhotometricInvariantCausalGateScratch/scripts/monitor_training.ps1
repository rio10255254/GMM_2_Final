param([int]$RefreshSeconds = 2)

$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ActivePath = Join-Path $Root "runs\active_run.json"
$LauncherPath = Join-Path $Root "logs\launcher_state.json"
$NvidiaSmi = "C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
if (-not (Test-Path -LiteralPath $NvidiaSmi)) {
    $NvidiaSmi = Get-ChildItem -LiteralPath "C:\Windows\System32\DriverStore\FileRepository" -Filter "nvidia-smi.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}

function Format-Duration([double]$Seconds) {
    if ($Seconds -lt 0 -or [double]::IsNaN($Seconds)) { return "--" }
    $Span = [TimeSpan]::FromSeconds($Seconds)
    if ($Span.TotalHours -ge 1) { return ("{0:00}:{1:00}:{2:00}" -f [math]::Floor($Span.TotalHours), $Span.Minutes, $Span.Seconds) }
    return ("{0:00}:{1:00}" -f $Span.Minutes, $Span.Seconds)
}

function Value-OrDash($Value, [string]$Format = "0.0000") {
    if ($null -eq $Value -or "$Value" -eq "") { return "--" }
    try { return ([double]$Value).ToString($Format) } catch { return "$Value" }
}

while ($true) {
    Clear-Host
    Write-Host "R104 FORMAL TRAINING" -ForegroundColor Cyan
    Write-Host "Live status and rolling ETA" -ForegroundColor DarkGray
    Write-Host ""
    if (-not (Test-Path -LiteralPath $ActivePath)) {
        Write-Host "Waiting for the trainer to publish its first status..." -ForegroundColor Yellow
        if (Test-Path -LiteralPath $LauncherPath) {
            $Launcher = Get-Content -Raw -LiteralPath $LauncherPath | ConvertFrom-Json
            Write-Host ("Trainer PID : {0}" -f $Launcher.trainer_pid)
        }
        Start-Sleep -Seconds $RefreshSeconds
        continue
    }
    $State = Get-Content -Raw -LiteralPath $ActivePath | ConvertFrom-Json
    $Epoch = if ($State.current_epoch) { [int]$State.current_epoch } else { [int]$State.completed_epoch }
    $Total = [int]$State.planned_epochs
    $Step = if ($State.current_step) { [int]$State.current_step } else { 0 }
    $Steps = if ($State.epoch_steps) { [int]$State.epoch_steps } else { 0 }
    $Fraction = if ($Steps -gt 0 -and $State.current_epoch) { (($Epoch - 1) + $Step / $Steps) / $Total } else { [int]$State.completed_epoch / [math]::Max($Total, 1) }
    $BarWidth = 30
    $Filled = [math]::Min($BarWidth, [math]::Max(0, [math]::Floor($Fraction * $BarWidth)))
    $Bar = ("#" * $Filled) + ("." * ($BarWidth - $Filled))
    Write-Host ("Status      : {0}" -f $State.status)
    Write-Host ("Epoch       : {0}/{1}  Step {2}/{3}" -f $Epoch, $Total, $Step, $Steps)
    Write-Host ("Progress    : [{0}] {1,5:0.0}%" -f $Bar, ($Fraction * 100)) -ForegroundColor Green
    $EpochLeft = if ($State.epoch_remaining_seconds) { [double]$State.epoch_remaining_seconds } else { 0 }
    $TotalLeft = if ($State.overall_remaining_seconds) { [double]$State.overall_remaining_seconds } elseif ($State.estimated_remaining_seconds) { [double]$State.estimated_remaining_seconds } else { 0 }
    Write-Host ("Epoch ETA   : {0}" -f (Format-Duration $EpochLeft))
    Write-Host ("Overall ETA : {0}" -f (Format-Duration $TotalLeft))
    if ($State.eta_method) { Write-Host ("ETA basis   : rolling median, up to 8 epochs") -ForegroundColor DarkGray }
    Write-Host ""
    $Train = $State.latest_train_metrics
    $Metrics = $State.latest_validation.metrics
    Write-Host "LATEST MEASUREMENTS" -ForegroundColor Cyan
    Write-Host ("Train loss  : {0}" -f (Value-OrDash $Train.total "0.00000"))
    Write-Host ("Val / Raw   : {0} / {1}" -f (Value-OrDash $Metrics.mae "0.00000"), (Value-OrDash $Metrics.raw_mae "0.00000"))
    Write-Host ("Boundary    : {0}    Texture: {1}" -f (Value-OrDash $Metrics.boundary_mae "0.00000"), (Value-OrDash $Metrics.texture_mae "0.00000"))
    Write-Host ("Gate split  : {0}    Identity: {1}" -f (Value-OrDash $Metrics.gate_separation "0.0000"), (Value-OrDash $Metrics.identity_change "0.00000"))
    Write-Host ("Motion      : {0}    Tile: {1}" -f (Value-OrDash $Metrics.objective_translation "0.00000"), (Value-OrDash $Metrics.objective_tile "0.00000"))
    Write-Host ""
    Write-Host "RUNTIME" -ForegroundColor Cyan
    Write-Host ("GPU peak    : {0} GiB" -f (Value-OrDash $State.gpu_peak_allocated_gib "0.0"))
    Write-Host ("GPU free    : {0} GiB" -f (Value-OrDash $State.gpu_free_end_gib "0.0"))
    if ($NvidiaSmi -and (Test-Path -LiteralPath $NvidiaSmi)) {
        $Gpu = & $NvidiaSmi --query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.free --format=csv,noheader,nounits 2>$null
        if ($Gpu) { Write-Host ("GPU live    : {0}  [use%, C, used/free MiB]" -f $Gpu) }
    }
    Write-Host ("Updated     : {0}" -f $State.updated_at) -ForegroundColor DarkGray
    if ($State.status -eq "completed") {
        Write-Host ""
        Write-Host "Training completed." -ForegroundColor Green
        break
    }
    if ($State.status -eq "failed") {
        Write-Host ""
        Write-Host "Training failed. See the preserved failure record." -ForegroundColor Red
        break
    }
    Start-Sleep -Seconds $RefreshSeconds
}
