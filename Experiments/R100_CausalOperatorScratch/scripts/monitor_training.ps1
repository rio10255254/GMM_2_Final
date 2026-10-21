param(
    [int]$RefreshSeconds = 3,
    [switch]$Once
)

$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DesignPath = Join-Path $Root "config\experiment_design.json"
$PolicyPath = Join-Path $Root "config\execution_policy.json"
$BenchmarkPath = Join-Path $Root "reports\final_execution_verification.json"
$ActivePath = Join-Path $Root "runs\active_run.json"
$LauncherPath = Join-Path $Root "logs\launcher_state.json"
$NvidiaSmi = "C:\Windows\System32\DriverStore\FileRepository\nv_dispwi.inf_amd64_9d6b008f0a7ed9e5\nvidia-smi.exe"

function Read-JsonSafe([string]$Path) {
    try {
        if (Test-Path -LiteralPath $Path) {
            return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
        }
    } catch {}
    return $null
}

function Get-Median($Values) {
    $Numbers = @($Values | ForEach-Object { if ($_ -ne $null -and "$_" -ne "") { [double]$_ } } | Sort-Object)
    if ($Numbers.Count -eq 0) { return $null }
    $Middle = [int][Math]::Floor($Numbers.Count / 2)
    if ($Numbers.Count % 2) { return $Numbers[$Middle] }
    return 0.5 * ($Numbers[$Middle - 1] + $Numbers[$Middle])
}

function Format-Duration([double]$Seconds) {
    if ($Seconds -lt 0 -or [double]::IsNaN($Seconds)) { return "--" }
    $Span = [TimeSpan]::FromSeconds($Seconds)
    if ($Span.TotalHours -ge 24) { return ("{0}d {1:00}h" -f [int][Math]::Floor($Span.TotalDays), $Span.Hours) }
    if ($Span.TotalHours -ge 1) { return ("{0:00}h {1:00}m" -f [int][Math]::Floor($Span.TotalHours), $Span.Minutes) }
    return ("{0:00}m {1:00}s" -f $Span.Minutes, $Span.Seconds)
}

function Get-Stage($Design, [int]$Epoch, $Policy) {
    foreach ($Stage in @($Design.training.stages)) {
        if ($Epoch -ge [int]$Stage.epoch_start -and $Epoch -le [int]$Stage.epoch_end) {
            $Patch = [int]$Stage.patch_size
            $Core = [int]$Stage.core_size
            $Batch = [int]$Stage.scene_batch_size
            if ($Policy -ne $null -and $Policy.scene_batch_overrides.PSObject.Properties.Name -contains "$Patch") {
                $Batch = [int]$Policy.scene_batch_overrides."$Patch"
            }
            $Every = [int]$Stage.alternate_every_epochs
            if ($Every -gt 0 -and (($Epoch - [int]$Stage.epoch_start + 1) % $Every) -eq 0) {
                $Patch = [int]$Stage.alternate_patch_size
                $Core = [int]$Stage.alternate_core_size
                $Batch = [int]$Stage.alternate_scene_batch_size
                if ($Policy -ne $null -and $Policy.scene_batch_overrides.PSObject.Properties.Name -contains "$Patch") {
                    $Batch = [int]$Policy.scene_batch_overrides."$Patch"
                }
            }
            return [pscustomobject]@{ patch = $Patch; core = $Core; batch = $Batch }
        }
    }
    return $null
}

function Get-BenchmarkEpochSeconds($Benchmark, [int]$Patch, [int]$Batch) {
    if ($Benchmark -eq $null) { return $null }
    $Rows = @($Benchmark.measurements | Where-Object {
        $_.status -eq "passed" -and [int]$_.patch_size -eq $Patch -and [int]$_.scene_batch -eq $Batch
    })
    if ($Rows.Count -eq 0) { return $null }
    $RegularScenes = 856
    $RegularBatches = [Math]::Ceiling($RegularScenes / [double]$Batch)
    $BundleBatches = [Math]::Max(1, [Math]::Round($RegularBatches * 0.16 / 0.84))
    return [double]$Rows[0].seconds_per_step * ($RegularBatches + $BundleBatches)
}

function Get-EpochEstimate($Rows, $Benchmark, $Design, $Policy, [int]$Epoch) {
    $Stage = Get-Stage $Design $Epoch $Policy
    if ($Stage -eq $null) { return 0.0 }
    $SamePatch = @($Rows | Where-Object { [int]$_.patch -eq [int]$Stage.patch })
    $BaseRows = @($SamePatch | Where-Object { "$( $_.val_reference_score )" -eq "" })
    if ($BaseRows.Count -eq 0) { $BaseRows = $SamePatch }
    if ($BaseRows.Count -gt 8) { $BaseRows = @($BaseRows | Select-Object -Last 8) }
    $Base = Get-Median ($BaseRows | ForEach-Object { $_.seconds })
    if ($Base -eq $null) { $Base = Get-BenchmarkEpochSeconds $Benchmark $Stage.patch $Stage.batch }
    if ($Base -eq $null) { $Base = 240.0 }

    $ValidationEvery = [int]$Design.training.validation_every_epochs
    $IsValidation = ($Epoch -eq 1 -or $Epoch -eq [int]$Design.training.epochs -or $Epoch % $ValidationEvery -eq 0)
    if ($IsValidation) {
        $ValRows = @($SamePatch | Where-Object { "$( $_.val_reference_score )" -ne "" })
        $ValMedian = Get-Median ($ValRows | ForEach-Object { $_.seconds })
        if ($ValMedian -ne $null) {
            $Base += [Math]::Max(0.0, $ValMedian - $Base)
        } else {
            $Base *= 1.18
        }
    }
    return [double]$Base
}

function Get-Bar([int]$Done, [int]$Total, [int]$Width) {
    $Inner = [Math]::Max(12, $Width - 2)
    $Fraction = if ($Total -gt 0) { [Math]::Min(1.0, $Done / [double]$Total) } else { 0.0 }
    $Filled = [int][Math]::Round($Inner * $Fraction)
    return "[" + ("#" * $Filled) + ("." * ($Inner - $Filled)) + "]"
}

function Value-OrDash($Value, [string]$Format = "0.0000") {
    if ($Value -eq $null -or "$Value" -eq "") { return "--" }
    return ([double]$Value).ToString($Format)
}

$Design = Read-JsonSafe $DesignPath
$Policy = Read-JsonSafe $PolicyPath
$Benchmark = Read-JsonSafe $BenchmarkPath
$FinishedFrames = 0

while ($true) {
    $State = Read-JsonSafe $ActivePath
    $Launcher = Read-JsonSafe $LauncherPath
    $Planned = if ($State -ne $null) { [int]$State.planned_epochs } elseif ($Design -ne $null) { [int]$Design.training.epochs } else { 0 }
    $Completed = if ($State -ne $null) { [int]$State.completed_epoch } else { 0 }
    $Status = if ($State -ne $null) { "$($State.status)" } elseif ($Launcher -ne $null) { "$($Launcher.status)" } else { "waiting" }
    $TrainerPid = if ($Launcher -ne $null) { [int]$Launcher.trainer_pid } else { 0 }
    $Alive = $false
    if ($TrainerPid -gt 0) { $Alive = $null -ne (Get-Process -Id $TrainerPid -ErrorAction SilentlyContinue) }

    $LogPath = if ($State -ne $null) { "$($State.training_log)" } else { "" }
    if (-not $LogPath -and $State -ne $null -and $State.run_id) {
        $Candidate = Get-ChildItem -Recurse -Filter training_log.csv -LiteralPath (Join-Path $Root "runs") | Where-Object { $_.FullName -match [regex]::Escape("$($State.run_id)") } | Select-Object -First 1
        if ($Candidate) { $LogPath = $Candidate.FullName }
    }
    $Rows = @()
    if ($LogPath -and (Test-Path -LiteralPath $LogPath)) {
        try { $Rows = @(Import-Csv -LiteralPath $LogPath) } catch { $Rows = @() }
    }
    $Latest = if ($Rows.Count -gt 0) { $Rows[-1] } else { $null }
    $NextEpoch = [Math]::Min($Planned, $Completed + 1)
    $Stage = if ($Design -ne $null -and $NextEpoch -gt 0) { Get-Stage $Design $NextEpoch $Policy } else { $null }
    $HeartbeatPath = if ($LogPath) { Join-Path (Split-Path -Parent $LogPath) "epoch_heartbeat.json" } else { "" }
    $Heartbeat = if ($HeartbeatPath) { Read-JsonSafe $HeartbeatPath } else { $null }
    $HeartbeatAge = if ($Heartbeat -ne $null -and $Heartbeat.updated_at) { [Math]::Max(0.0, ((Get-Date) - [datetime]$Heartbeat.updated_at).TotalSeconds) } else { [double]::PositiveInfinity }
    $HeartbeatCurrent = $Heartbeat -ne $null -and [int]$Heartbeat.epoch -eq $NextEpoch
    $HeartbeatPhase = if ($Heartbeat -ne $null) { "$($Heartbeat.phase)" } else { "waiting" }
    $HeartbeatActive = $HeartbeatCurrent -and $HeartbeatPhase -in @("training", "validation", "checkpoint")
    $Stalled = $Alive -and $HeartbeatActive -and $HeartbeatAge -gt 90.0

    $Remaining = 0.0
    if ($Completed -lt $Planned -and $Design -ne $null) {
        $CurrentEstimate = Get-EpochEstimate $Rows $Benchmark $Design $Policy ($Completed + 1)
        $Anchor = if ($Latest -ne $null -and $LogPath) { (Get-Item -LiteralPath $LogPath).LastWriteTime } elseif ($State -ne $null -and $State.started_at) { [datetime]$State.started_at } elseif ($Launcher -ne $null) { [datetime]$Launcher.launched_at } else { Get-Date }
        $ElapsedCurrent = [Math]::Max(0.0, ((Get-Date) - $Anchor).TotalSeconds)
        if ($HeartbeatCurrent -and $Heartbeat.epoch_started_at) {
            $ElapsedCurrent = [Math]::Max(0.0, ((Get-Date) - [datetime]$Heartbeat.epoch_started_at).TotalSeconds)
        }
        if ($HeartbeatCurrent -and $HeartbeatPhase -eq "training" -and [int]$Heartbeat.total_batches -gt 0 -and [int]$Heartbeat.batch_index -gt 0) {
            $Fraction = [Math]::Min(1.0, [int]$Heartbeat.batch_index / [double][int]$Heartbeat.total_batches)
            $ObservedProjection = $ElapsedCurrent / [Math]::Max($Fraction, 0.01)
            $ProjectedCurrent = [Math]::Max($CurrentEstimate, $ObservedProjection)
            $Remaining += [Math]::Max(0.0, $ProjectedCurrent - $ElapsedCurrent)
        } elseif ($Stalled) {
            $Remaining += $CurrentEstimate
        } else {
            $Remaining += [Math]::Max(0.0, $CurrentEstimate - $ElapsedCurrent)
        }
        for ($Epoch = $Completed + 2; $Epoch -le $Planned; $Epoch++) {
            $Remaining += Get-EpochEstimate $Rows $Benchmark $Design $Policy $Epoch
        }
    }
    $Low = $Remaining * 0.88
    $High = $Remaining * 1.18
    $Eta = (Get-Date).AddSeconds($Remaining)

    $Gpu = "GPU --"
    $GpuCritical = $false
    if (Test-Path -LiteralPath $NvidiaSmi) {
        $GpuLine = & $NvidiaSmi --query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu --format=csv,noheader,nounits 2>$null
        if ($GpuLine) {
            $Parts = $GpuLine -split "," | ForEach-Object { $_.Trim() }
            $Gpu = "GPU $($Parts[0])%  VRAM $($Parts[1])/$([int]$Parts[1] + [int]$Parts[2]) MiB  $($Parts[3]) C"
            $GpuCritical = [int]$Parts[2] -lt 512
        }
    }

    $Width = 78
    try { $Width = [Math]::Max(58, [Math]::Min(100, $Host.UI.RawUI.WindowSize.Width - 1)) } catch {}
    Clear-Host
    Write-Host "R100 TRAINING" -ForegroundColor Cyan
    $Health = if (-not $Alive -and $Status -notin @("complete", "failed")) { "STOPPED" } elseif ($Stalled) { "STALLED" } elseif ($GpuCritical) { "VRAM CRITICAL" } else { "healthy" }
    $HealthColor = if ($Health -eq "healthy") { "White" } else { "Red" }
    Write-Host ("State {0}   PID {1}   alive {2}   {3}" -f $Status, $TrainerPid, $Alive, $Health) -ForegroundColor $HealthColor
    Write-Host (Get-Bar $Completed $Planned $Width) -ForegroundColor Green
    Write-Host ("Epoch {0}/{1}   next {2}   {3}" -f $Completed, $Planned, $NextEpoch, $(if ($Stage) { "patch $($Stage.patch) core $($Stage.core) batch $($Stage.batch)" } else { "stage --" }))
    Write-Host $Gpu -ForegroundColor Yellow
    if ($HeartbeatCurrent) {
        $Beat = if ([double]::IsPositiveInfinity($HeartbeatAge)) { "--" } else { (Format-Duration $HeartbeatAge) }
        if ($HeartbeatPhase -eq "training" -and [int]$Heartbeat.total_batches -gt 0) {
            $Percent = 100.0 * [int]$Heartbeat.batch_index / [double][int]$Heartbeat.total_batches
            Write-Host ("Current E{0} training  batch {1}/{2}  {3:0.0}%  heartbeat {4}" -f $Heartbeat.epoch, $Heartbeat.batch_index, $Heartbeat.total_batches, $Percent, $Beat) -ForegroundColor Cyan
        } else {
            Write-Host ("Current E{0} {1}  heartbeat {2}" -f $Heartbeat.epoch, $HeartbeatPhase, $Beat) -ForegroundColor Cyan
        }
    }
    if ($Stalled) {
        Write-Host "No progress heartbeat for over 90 seconds. ETA is suspended until progress resumes." -ForegroundColor Red
    }
    if ($Completed -lt $Planned -and -not $Stalled) {
        Write-Host ("Left {0}   range {1} - {2}" -f (Format-Duration $Remaining), (Format-Duration $Low), (Format-Duration $High)) -ForegroundColor Yellow
        Write-Host ("ETA  {0}" -f $Eta.ToString("MM-dd HH:mm:ss")) -ForegroundColor Yellow
    }
    if ($Latest -ne $null) {
        Write-Host ""
        Write-Host ("Last E{0}  {1}  loss {2}" -f $Latest.epoch, (Format-Duration ([double]$Latest.seconds)), (Value-OrDash $Latest.train_total)) -ForegroundColor White
        Write-Host ("Contour {0}  edge symmetry {1}  boundary exclusion {2}" -f (Value-OrDash $Latest.train_boundary_normal_distance), (Value-OrDash $Latest.train_edge_evenness), (Value-OrDash $Latest.train_texture_boundary_exclusion))
        Write-Host ("Material {0}  motion {1}  tile {2}" -f (Value-OrDash $Latest.train_material_detail_recovery), (Value-OrDash $Latest.train_displacement), (Value-OrDash $Latest.train_consistency))
        if ("$($Latest.val_reference_score)" -ne "") {
            Write-Host ("Validation  detail {0}  contour {1}  motion {2}  tile {3}" -f (Value-OrDash $Latest.val_detail_axis), (Value-OrDash $Latest.val_contour_axis), (Value-OrDash $Latest.val_motion_axis), (Value-OrDash $Latest.val_tile_axis)) -ForegroundColor Magenta
        }
    } else {
        Write-Host ""
        Write-Host "Initializing the first epoch; ETA uses measured preflight speed." -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host ("Dynamic estimate uses committed epochs plus live batch heartbeat. Refresh {0}s." -f $RefreshSeconds) -ForegroundColor DarkGray
    Write-Host "Closing this window does not stop training." -ForegroundColor DarkGray

    if ($Once) { break }

    if ($Status -in @("complete", "failed") -or ($Completed -ge $Planned -and $Planned -gt 0)) {
        $FinishedFrames++
        if ($FinishedFrames -ge 4) { break }
    } else {
        $FinishedFrames = 0
    }
    Start-Sleep -Seconds ([Math]::Max(1, $RefreshSeconds))
}

Write-Host ""
Write-Host "Monitor finished." -ForegroundColor Cyan
