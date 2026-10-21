param([int]$RefreshSeconds = 2)

$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Active = Join-Path $Root "runs\active_run.json"
$Registry = Join-Path $Root "runs\formal_run_registry.json"
$Launcher = Join-Path $Root "logs\launcher_state.json"
$ConfigPath = Join-Path $Root "config\experiment.json"

function Format-Time([double]$Seconds) {
    if ([double]::IsNaN($Seconds) -or [double]::IsInfinity($Seconds) -or $Seconds -lt 0) { return "calculating" }
    $Span = [TimeSpan]::FromSeconds($Seconds)
    if ($Span.TotalDays -ge 1) { return ("{0}d {1:00}h {2:00}m" -f [math]::Floor($Span.TotalDays), $Span.Hours, $Span.Minutes) }
    if ($Span.TotalHours -ge 1) { return ("{0}h {1:00}m" -f [math]::Floor($Span.TotalHours), $Span.Minutes) }
    return ("{0}m {1:00}s" -f [math]::Floor($Span.TotalMinutes), $Span.Seconds)
}

function Read-Json($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json } catch { return $null }
}

function Stage-Cost([int]$Epoch, $Config) {
    if ($Config -and $Config.training -and $Config.training.stages) {
        foreach ($Stage in @($Config.training.stages)) {
            if ($Epoch -ge [int]$Stage.start -and $Epoch -le [int]$Stage.end) {
                return [math]::Pow([double]$Stage.patch_size, 2)
            }
        }
    }
    return 65536.0
}

function Epoch-Estimate($State, $LogRows, $Config) {
    $Current = [int]$State.current_epoch
    $Planned = [int]$State.planned_epochs
    if ($Current -le 0 -or $Planned -le 0) { return [double]::NaN }
    $StepRemain = [double]$State.epoch_remaining_seconds
    $Recent = @($LogRows | Select-Object -Last 6 | ForEach-Object { [double]$_.seconds } | Where-Object { $_ -gt 0 })
    $CommittedMedian = [double]::NaN
    if ($Recent.Count -gt 0) {
        $Sorted = @($Recent | Sort-Object)
        $CommittedMedian = if ($Sorted.Count % 2) { $Sorted[[int]($Sorted.Count / 2)] } else { 0.5 * ($Sorted[$Sorted.Count / 2 - 1] + $Sorted[$Sorted.Count / 2]) }
    }
    $ProjectedCurrent = [double]::NaN
    if ($State.current_step -gt 0 -and $State.epoch_steps -gt 0 -and [double]$State.seconds_per_step -gt 0) {
        $ProjectedCurrent = [double]$State.seconds_per_step * [double]$State.epoch_steps
    }
    if ([double]::IsNaN($ProjectedCurrent)) { $ProjectedCurrent = $CommittedMedian }
    elseif (-not [double]::IsNaN($CommittedMedian)) { $ProjectedCurrent = 0.75 * $ProjectedCurrent + 0.25 * $CommittedMedian }
    if ([double]::IsNaN($ProjectedCurrent)) { return [double]::NaN }
    $CurrentCost = Stage-Cost $Current $Config
    $ValidationEvery = if ($Config -and $Config.training.validation_every_epochs) { [int]$Config.training.validation_every_epochs } else { 2 }
    $ValidationOverhead = 14.0
    $Remaining = [math]::Max($StepRemain, 0)
    if ($State.current_step -ge $State.epoch_steps -and ($Current -eq 1 -or $Current % $ValidationEvery -eq 0)) { $Remaining += $ValidationOverhead }
    for ($Epoch = $Current + 1; $Epoch -le $Planned; $Epoch++) {
        $Ratio = (Stage-Cost $Epoch $Config) / [math]::Max($CurrentCost, 1.0)
        $Remaining += $ProjectedCurrent * $Ratio
        if ($Epoch -eq 1 -or $Epoch % $ValidationEvery -eq 0 -or $Epoch -eq $Planned) { $Remaining += $ValidationOverhead }
    }
    return $Remaining
}

$Host.UI.RawUI.WindowTitle = "R103 Training Monitor"
$Config = Read-Json $ConfigPath
while ($true) {
    $State = Read-Json $Active
    $Launch = Read-Json $Launcher
    $Rows = @()
    if ($State -and $State.training_log -and (Test-Path -LiteralPath $State.training_log)) { $Rows = @(Import-Csv -LiteralPath $State.training_log) }
    elseif ($State -and $State.run_id) {
        $Candidate = Join-Path (Join-Path $Root "runs\$($State.run_id)") "training_log.csv"
        if (Test-Path -LiteralPath $Candidate) { $Rows = @(Import-Csv -LiteralPath $Candidate) }
    }
    Clear-Host
    Write-Host "R103  UNIVERSAL DETAIL TRAINING" -ForegroundColor Cyan
    Write-Host ""
    if (-not $State) {
        Write-Host "Waiting for trainer state..." -ForegroundColor Yellow
        if ($Launch) { Write-Host ("Launcher PID {0}  {1}" -f $Launch.trainer_pid, $Launch.status) }
        Start-Sleep -Seconds $RefreshSeconds
        continue
    }
    $Epoch = if ($State.current_epoch) { [int]$State.current_epoch } else { [int]$State.completed_epoch }
    $Planned = [int]$State.planned_epochs
    $Step = [int]$State.current_step
    $Steps = [int]$State.epoch_steps
    $Fraction = if ($Planned -gt 0) { ([math]::Max($Epoch - 1, 0) + $(if ($Steps -gt 0) { $Step / $Steps } else { 0 })) / $Planned } else { 0 }
    $BarWidth = 32
    $Filled = [math]::Min($BarWidth, [math]::Max(0, [math]::Round($Fraction * $BarWidth)))
    $Bar = ("#" * $Filled) + ("." * ($BarWidth - $Filled))
    $Eta = Epoch-Estimate $State $Rows $Config
    Write-Host ("[{0}] {1,6:P1}" -f $Bar, $Fraction) -ForegroundColor Green
    Write-Host ("Epoch  {0}/{1}    Step  {2}/{3}" -f $Epoch, $Planned, $Step, $Steps)
    Write-Host ("ETA    {0}    Epoch left {1}" -f (Format-Time $Eta), (Format-Time ([double]$State.epoch_remaining_seconds)))
    Write-Host ("State  {0}    PID {1}" -f $State.status, $State.trainer_pid)
    if ($Rows.Count -gt 0) {
        $Last = $Rows[-1]
        Write-Host ""
        Write-Host ("Last committed epoch {0}  {1}s" -f $Last.epoch, [math]::Round([double]$Last.seconds, 1)) -ForegroundColor White
        Write-Host ("Loss {0:N4}   PSNR {1:N2} dB" -f [double]$Last.train_total, [double]$Last.validation_psnr_db)
        Write-Host ("Contour {0:N3}  Texture {1:N3}" -f [double]$Last.validation_contour, [double]$Last.validation_texture)
        Write-Host ("Identity {0:N3} Tile {1:N3}" -f [double]$Last.validation_identity, [double]$Last.validation_tile_consistency)
        Write-Host ("GPU peak {0:N1} GiB  Free {1:N1} GiB" -f [double]$Last.gpu_peak_allocated_gib, [double]$Last.gpu_free_end_gib)
    }
    Write-Host ""
    Write-Host "Closing this window does not stop training." -ForegroundColor DarkGray
    if ($State.status -in @("completed", "failed")) {
        Write-Host ("Training {0}." -f $State.status) -ForegroundColor $(if ($State.status -eq "completed") { "Green" } else { "Red" })
        break
    }
    Start-Sleep -Seconds $RefreshSeconds
}
Read-Host "Press Enter to close"
