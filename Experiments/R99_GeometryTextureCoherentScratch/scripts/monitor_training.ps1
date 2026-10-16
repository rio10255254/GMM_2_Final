param(
    [int]$RefreshSeconds = 3,
    [switch]$Once
)

$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DesignPath = Join-Path $Root "config\experiment_design.json"
$PolicyPath = Join-Path $Root "config\execution_policy.json"
$BenchmarkPath = Join-Path $Root "reports\acceleration_benchmark.json"
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

    $Remaining = 0.0
    if ($Completed -lt $Planned -and $Design -ne $null) {
        $CurrentEstimate = Get-EpochEstimate $Rows $Benchmark $Design $Policy ($Completed + 1)
        $Anchor = if ($Latest -ne $null -and $LogPath) { (Get-Item -LiteralPath $LogPath).LastWriteTime } elseif ($State -ne $null -and $State.started_at) { [datetime]$State.started_at } elseif ($Launcher -ne $null) { [datetime]$Launcher.launched_at } else { Get-Date }
        $ElapsedCurrent = [Math]::Max(0.0, ((Get-Date) - $Anchor).TotalSeconds)
        $Remaining += [Math]::Max(0.0, $CurrentEstimate - $ElapsedCurrent)
        for ($Epoch = $Completed + 2; $Epoch -le $Planned; $Epoch++) {
            $Remaining += Get-EpochEstimate $Rows $Benchmark $Design $Policy $Epoch
        }
    }
    $Low = $Remaining * 0.88
    $High = $Remaining * 1.18
    $Eta = (Get-Date).AddSeconds($Remaining)

    $Gpu = "GPU --"
    if (Test-Path -LiteralPath $NvidiaSmi) {
        $GpuLine = & $NvidiaSmi --query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu --format=csv,noheader,nounits 2>$null
        if ($GpuLine) {
            $Parts = $GpuLine -split "," | ForEach-Object { $_.Trim() }
            $Gpu = "GPU $($Parts[0])%  VRAM $($Parts[1])/$([int]$Parts[1] + [int]$Parts[2]) MiB  $($Parts[3]) C"
        }
    }

    $Width = 78
    try { $Width = [Math]::Max(58, [Math]::Min(100, $Host.UI.RawUI.WindowSize.Width - 1)) } catch {}
    Clear-Host
    Write-Host "R99 TRAINING" -ForegroundColor Cyan
    Write-Host ("State {0}   PID {1}   alive {2}" -f $Status, $TrainerPid, $Alive) -ForegroundColor White
    Write-Host (Get-Bar $Completed $Planned $Width) -ForegroundColor Green
    Write-Host ("Epoch {0}/{1}   next {2}   {3}" -f $Completed, $Planned, $NextEpoch, $(if ($Stage) { "patch $($Stage.patch) core $($Stage.core) batch $($Stage.batch)" } else { "stage --" }))
    Write-Host $Gpu -ForegroundColor Yellow
    if ($Completed -lt $Planned) {
        Write-Host ("Left {0}   range {1} - {2}" -f (Format-Duration $Remaining), (Format-Duration $Low), (Format-Duration $High)) -ForegroundColor Yellow
        Write-Host ("ETA  {0}" -f $Eta.ToString("MM-dd HH:mm:ss")) -ForegroundColor Yellow
    }
    if ($Latest -ne $null) {
        Write-Host ""
        Write-Host ("Last E{0}  {1}  loss {2}" -f $Latest.epoch, (Format-Duration ([double]$Latest.seconds)), (Value-OrDash $Latest.train_total)) -ForegroundColor White
        Write-Host ("Contour dist {0}  transport {1}px  align {2}" -f (Value-OrDash $Latest.train_boundary_normal_distance), (Value-OrDash $Latest.train_transport_abs_px), (Value-OrDash $Latest.train_transport_alignment))
        Write-Host ("Detail {0}  motion {1}  tile {2}" -f (Value-OrDash $Latest.train_detail_l1), (Value-OrDash $Latest.train_displacement), (Value-OrDash $Latest.train_consistency))
        if ("$($Latest.val_reference_score)" -ne "") {
            Write-Host ("Validation  detail {0}  contour {1}  motion {2}  tile {3}" -f (Value-OrDash $Latest.val_detail_axis), (Value-OrDash $Latest.val_contour_axis), (Value-OrDash $Latest.val_motion_axis), (Value-OrDash $Latest.val_tile_axis)) -ForegroundColor Magenta
        }
    } else {
        Write-Host ""
        Write-Host "Initializing the first epoch; ETA uses measured preflight speed." -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host ("Dynamic estimate updates after every committed epoch. Refresh {0}s." -f $RefreshSeconds) -ForegroundColor DarkGray
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
