param(
    [int]$RefreshSeconds = 3
)

$Root = Split-Path -Parent $PSScriptRoot
$Active = Join-Path $Root "runs\launcher_logs\active_formal_run.json"
$Stdout = Join-Path $Root "runs\launcher_logs\formal_stdout.log"
$Stderr = Join-Path $Root "runs\launcher_logs\formal_stderr.log"
$DesignPath = Join-Path $Root "config\experiment_design.json"
$NvidiaSmi = "C:\Windows\System32\DriverStore\FileRepository\nv_dispwi.inf_amd64_9d6b008f0a7ed9e5\nvidia-smi.exe"
$Design = Get-Content -LiteralPath $DesignPath -Raw -Encoding UTF8 | ConvertFrom-Json

try {
    $MaximumWindow = $Host.UI.RawUI.MaxPhysicalWindowSize
    $TargetWidth = [Math]::Min(108, $MaximumWindow.Width)
    $TargetHeight = [Math]::Min(42, $MaximumWindow.Height)
    $Buffer = $Host.UI.RawUI.BufferSize
    if ($Buffer.Width -lt $TargetWidth) { $Buffer.Width = $TargetWidth }
    if ($Buffer.Height -lt 300) { $Buffer.Height = 300 }
    $Host.UI.RawUI.BufferSize = $Buffer
    $Window = $Host.UI.RawUI.WindowSize
    $Window.Width = $TargetWidth
    $Window.Height = $TargetHeight
    $Host.UI.RawUI.WindowSize = $Window
} catch {
    # Some terminal hosts manage their own dimensions; the dashboard still works.
}

function Format-Duration {
    param([double]$Seconds)
    if ([double]::IsNaN($Seconds) -or [double]::IsInfinity($Seconds) -or $Seconds -lt 0) {
        return "estimating..."
    }
    $Span = [TimeSpan]::FromSeconds([Math]::Round($Seconds))
    if ($Span.TotalDays -ge 1) {
        return ("{0}d {1:00}:{2:00}:{3:00}" -f [int][Math]::Floor($Span.TotalDays), $Span.Hours, $Span.Minutes, $Span.Seconds)
    }
    return ("{0:00}:{1:00}:{2:00}" -f [int][Math]::Floor($Span.TotalHours), $Span.Minutes, $Span.Seconds)
}

function Format-ProgressBar {
    param([double]$Fraction, [int]$Width = 28, [double]$Maximum = 0.995)
    $SafeFraction = [Math]::Max(0.0, [Math]::Min($Maximum, $Fraction))
    $Filled = [Math]::Min($Width, [Math]::Max(0, [int][Math]::Floor($SafeFraction * $Width)))
    return "[" + ("#" * $Filled) + ("." * ($Width - $Filled)) + "]"
}

function Get-DashboardWidth {
    try {
        return [Math]::Max(76, [Math]::Min(104, $Host.UI.RawUI.WindowSize.Width - 1))
    } catch {
        return 92
    }
}

function Write-Rule {
    param([string]$Character = "-", [ConsoleColor]$Color = [ConsoleColor]::DarkGray)
    Write-Host ($Character * (Get-DashboardWidth)) -ForegroundColor $Color
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("  " + $Title) -ForegroundColor Cyan
    Write-Rule "-" DarkGray
}

function Write-Metric {
    param(
        [string]$Label,
        [string]$Value,
        [ConsoleColor]$Color = [ConsoleColor]::White
    )
    Write-Host ("  {0,-23}" -f ($Label + ":")) -NoNewline -ForegroundColor DarkGray
    Write-Host $Value -ForegroundColor $Color
}

function Get-Ewma {
    param([object[]]$Values, [double]$Alpha = 0.80)
    $Usable = @($Values | Where-Object { $null -ne $_ } | ForEach-Object { [double]$_ })
    if ($Usable.Count -eq 0) {
        return $null
    }
    $Estimate = [double]$Usable[0]
    for ($Index = 1; $Index -lt $Usable.Count; $Index++) {
        $Estimate = $Alpha * [double]$Usable[$Index] + (1.0 - $Alpha) * $Estimate
    }
    return [double]$Estimate
}

function Get-StagePatch {
    param([int]$Epoch)
    $Stage = @($Design.training.stages | Where-Object {
        $Epoch -ge [int]$_.epoch_start -and $Epoch -le [int]$_.epoch_end
    }) | Select-Object -First 1
    if ($null -eq $Stage) {
        return 512
    }
    return [int]$Stage.patch_size
}

function Get-BaseEpochSeconds {
    param([int]$TargetPatch, [object[]]$Rows)
    $TrainingOnly = @($Rows | Where-Object {
        [string]::IsNullOrWhiteSpace([string]$_.val_reference_score) -and [double]$_.seconds -gt 0
    })
    $SamePatch = @($TrainingOnly | Where-Object { [int]$_.patch -eq $TargetPatch } | ForEach-Object { [double]$_.seconds })
    $SameEstimate = Get-Ewma $SamePatch
    if ($null -ne $SameEstimate) {
        return [double]$SameEstimate
    }
    if ($TrainingOnly.Count -gt 0) {
        $SourcePatch = [Math]::Max(1, [int]$TrainingOnly[-1].patch)
        $SourceValues = @($TrainingOnly | Where-Object { [int]$_.patch -eq $SourcePatch } | ForEach-Object { [double]$_.seconds })
        $SourceEstimate = Get-Ewma $SourceValues
        return [double]$SourceEstimate * [Math]::Pow($TargetPatch / [double]$SourcePatch, 2.0)
    }
    $ValidationRows = @($Rows | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.val_reference_score) })
    if ($ValidationRows.Count -gt 0) {
        $SourcePatch = [Math]::Max(1, [int]$ValidationRows[-1].patch)
        $SourceValues = @($ValidationRows | Where-Object { [int]$_.patch -eq $SourcePatch } | ForEach-Object { [double]$_.seconds })
        return 0.62 * [double](Get-Ewma $SourceValues) * [Math]::Pow($TargetPatch / [double]$SourcePatch, 2.0)
    }
    return 240.0 * [Math]::Pow($TargetPatch / 512.0, 2.0)
}

function Get-ValidationOverheadSeconds {
    param([object[]]$Rows)
    $Candidates = @()
    $Patches = @($Rows | ForEach-Object { [int]$_.patch } | Sort-Object -Unique)
    foreach ($Patch in $Patches) {
        $TrainingValues = @($Rows | Where-Object {
            [int]$_.patch -eq $Patch -and [string]::IsNullOrWhiteSpace([string]$_.val_reference_score)
        } | ForEach-Object { [double]$_.seconds })
        $ValidationValues = @($Rows | Where-Object {
            [int]$_.patch -eq $Patch -and -not [string]::IsNullOrWhiteSpace([string]$_.val_reference_score)
        } | ForEach-Object { [double]$_.seconds })
        if ($TrainingValues.Count -eq 0 -or $ValidationValues.Count -eq 0) {
            continue
        }
        $Extra = [double](Get-Ewma $ValidationValues) - [double](Get-Ewma $TrainingValues)
        if ($Extra -gt 0) {
            $Candidates += $Extra
        }
    }
    $Estimate = Get-Ewma $Candidates
    if ($null -eq $Estimate) {
        return 90.0
    }
    return [double]$Estimate
}

function Test-ValidationEpoch {
    param([int]$Epoch, [int]$PlannedEpochs)
    $ValidationEvery = [Math]::Max(1, [int]$Design.training.validation_every_epochs)
    return ($Epoch -eq 1) -or ($Epoch % $ValidationEvery -eq 0) -or ($Epoch -eq $PlannedEpochs)
}

function Get-EpochEstimateSeconds {
    param([int]$Epoch, [int]$PlannedEpochs, [object[]]$Rows)
    $Patch = Get-StagePatch $Epoch
    $NeedsValidation = Test-ValidationEpoch $Epoch $PlannedEpochs
    $Fallback = Get-BaseEpochSeconds $Patch $Rows
    if ($NeedsValidation) {
        $Fallback += Get-ValidationOverheadSeconds $Rows
    }
    $BucketValues = @($Rows | Where-Object {
        [int]$_.patch -eq $Patch -and
        ((-not [string]::IsNullOrWhiteSpace([string]$_.val_reference_score)) -eq $NeedsValidation)
    } | ForEach-Object { [double]$_.seconds })
    if ($BucketValues.Count -eq 0) {
        return [double]$Fallback
    }
    $Direct = [double](Get-Ewma $BucketValues)
    if ($BucketValues.Count -eq 1) {
        return 0.45 * $Direct + 0.55 * $Fallback
    }
    if ($BucketValues.Count -eq 2) {
        return 0.75 * $Direct + 0.25 * $Fallback
    }
    return $Direct
}

function Get-EpochUncertaintySeconds {
    param([int]$Epoch, [int]$PlannedEpochs, [object[]]$Rows, [double]$Estimate)
    $Patch = Get-StagePatch $Epoch
    $NeedsValidation = Test-ValidationEpoch $Epoch $PlannedEpochs
    $BucketValues = @($Rows | Where-Object {
        [int]$_.patch -eq $Patch -and
        ((-not [string]::IsNullOrWhiteSpace([string]$_.val_reference_score)) -eq $NeedsValidation)
    } | ForEach-Object { [double]$_.seconds })
    if ($BucketValues.Count -eq 0) {
        return [Math]::Max(30.0, 0.20 * $Estimate)
    }
    if ($BucketValues.Count -lt 3) {
        return [Math]::Max(25.0, 0.12 * $Estimate)
    }
    $Forecast = [double]$BucketValues[0]
    $Residuals = @()
    for ($Index = 1; $Index -lt $BucketValues.Count; $Index++) {
        $Observed = [double]$BucketValues[$Index]
        $Residuals += [Math]::Abs($Forecast - $Observed)
        $Forecast = 0.80 * $Observed + 0.20 * $Forecast
    }
    $RecentError = Get-Ewma $Residuals 0.65
    return [Math]::Max(20.0, 1.65 * [double]$RecentError)
}

do {
    Clear-Host
    $Now = Get-Date
    Write-Rule "=" Cyan
    Write-Host ("  R93 TRAINING DASHBOARD    {0}" -f $Now.ToString("yyyy-MM-dd HH:mm:ss")) -ForegroundColor Cyan
    Write-Rule "=" Cyan
    $Rows = @()

    if (Test-Path -LiteralPath $Active) {
        try {
            $State = Get-Content -LiteralPath $Active -Raw | ConvertFrom-Json
            try { $Host.UI.RawUI.WindowTitle = "R93 - $($State.status) - Epoch $($State.completed_epoch)/$($State.planned_epochs)" } catch {}
            $RecordDirectory = Join-Path $Root ("runs\training_" + [string]$State.run_id)
            $TrainingLog = Join-Path $RecordDirectory "training_log.csv"
            if (Test-Path -LiteralPath $TrainingLog) {
                $Rows = @(Import-Csv -LiteralPath $TrainingLog)
            }

            Write-Section "RUN"
            $StatusText = ([string]$State.status).ToUpperInvariant()
            $StatusColor = if ($State.status -eq "active") { "Green" } elseif ($State.status -eq "complete") { "Cyan" } else { "Red" }
            Write-Metric "Status" $StatusText $StatusColor
            Write-Metric "Completed" ("{0} / {1} epochs" -f $State.completed_epoch, $State.planned_epochs)
            Write-Metric "Run" ([string]$State.run_id)

            if ($State.status -eq "active" -and [int]$State.completed_epoch -lt [int]$State.planned_epochs) {
                $CurrentEpoch = [int]$State.completed_epoch + 1
                $ProgressFile = Get-Item -LiteralPath $Active
                if ([int]$State.completed_epoch -eq 0) {
                    $EpochStarted = [datetime]$State.started_at
                } else {
                    $EpochStarted = $ProgressFile.LastWriteTime
                }
                $Elapsed = [Math]::Max(0.0, ((Get-Date) - $EpochStarted).TotalSeconds)
                $ExpectedCurrent = Get-EpochEstimateSeconds $CurrentEpoch ([int]$State.planned_epochs) $Rows
                $CurrentUncertainty = Get-EpochUncertaintySeconds $CurrentEpoch ([int]$State.planned_epochs) $Rows $ExpectedCurrent
                $ProgressFraction = if ($ExpectedCurrent -gt 0) { [Math]::Min(0.995, $Elapsed / $ExpectedCurrent) } else { 0.0 }
                $CurrentPatch = Get-StagePatch $CurrentEpoch
                $TrainingPhaseEstimate = Get-BaseEpochSeconds $CurrentPatch $Rows
                $NeedsValidation = Test-ValidationEpoch $CurrentEpoch ([int]$State.planned_epochs)
                $EstimatedPhase = if ($NeedsValidation -and $Elapsed -ge $TrainingPhaseEstimate) { "validation/checkpoint" } else { "training" }
                $EpochRemaining = [Math]::Max(0.0, $ExpectedCurrent - $Elapsed)
                $EpochRemainingLow = [Math]::Max(0.0, $ExpectedCurrent - $CurrentUncertainty - $Elapsed)
                $EpochRemainingHigh = [Math]::Max(0.0, $ExpectedCurrent + $CurrentUncertainty - $Elapsed)
                $TotalRemaining = $EpochRemaining
                $TotalVariance = $CurrentUncertainty * $CurrentUncertainty
                $ProjectedFutureStage = $false
                for ($FutureEpoch = $CurrentEpoch + 1; $FutureEpoch -le [int]$State.planned_epochs; $FutureEpoch++) {
                    $FutureEstimate = Get-EpochEstimateSeconds $FutureEpoch ([int]$State.planned_epochs) $Rows
                    $FutureUncertainty = Get-EpochUncertaintySeconds $FutureEpoch ([int]$State.planned_epochs) $Rows $FutureEstimate
                    $TotalRemaining += $FutureEstimate
                    $TotalVariance += $FutureUncertainty * $FutureUncertainty
                    $FuturePatch = Get-StagePatch $FutureEpoch
                    if (@($Rows | Where-Object { [int]$_.patch -eq $FuturePatch }).Count -eq 0) {
                        $ProjectedFutureStage = $true
                    }
                }
                $RandomBand = 1.65 * [Math]::Sqrt($TotalVariance)
                $SystematicFraction = if ($ProjectedFutureStage) { 0.12 } elseif ($Rows.Count -lt 6) { 0.08 } else { 0.03 }
                $TotalBand = [Math]::Max($RandomBand, $SystematicFraction * $TotalRemaining)
                $TotalRemainingLow = [Math]::Max(0.0, $TotalRemaining - $TotalBand)
                $TotalRemainingHigh = $TotalRemaining + $TotalBand
                $FinishAt = (Get-Date).AddSeconds($TotalRemaining)
                $FinishLow = (Get-Date).AddSeconds($TotalRemainingLow)
                $FinishHigh = (Get-Date).AddSeconds($TotalRemainingHigh)
                $Confidence = if ($Rows.Count -lt 3) { "early estimate" } elseif ($ProjectedFutureStage) { "future stage projected" } else { "recent-weighted, measured by stage" }

                Write-Section "LIVE PROGRESS"
                Write-Metric "Current epoch" ("{0} of {1}" -f $CurrentEpoch, $State.planned_epochs) Cyan
                Write-Metric "Estimated progress" ("{0}  {1,5:N1}%" -f (Format-ProgressBar $ProgressFraction 36), (100.0 * $ProgressFraction)) Green
                Write-Metric "Estimated phase" $EstimatedPhase Yellow
                Write-Metric "Elapsed this epoch" (Format-Duration $Elapsed)

                Write-Section "TIME REMAINING"
                Write-Metric "This epoch" (Format-Duration $EpochRemaining) Yellow
                Write-Metric "Likely epoch range" ("{0}  to  {1}" -f (Format-Duration $EpochRemainingLow), (Format-Duration $EpochRemainingHigh)) DarkYellow
                Write-Metric "Entire run" (Format-Duration $TotalRemaining) Yellow
                Write-Metric "Likely total range" ("{0}  to  {1}" -f (Format-Duration $TotalRemainingLow), (Format-Duration $TotalRemainingHigh)) DarkYellow
                Write-Metric "Expected finish" $FinishAt.ToString("yyyy-MM-dd HH:mm") Green
                Write-Metric "Likely finish window" ("{0}  to  {1}" -f $FinishLow.ToString("MM-dd HH:mm"), $FinishHigh.ToString("MM-dd HH:mm"))
                Write-Metric "Estimate quality" ("{0}; {1} measured epochs" -f $Confidence, $Rows.Count) DarkGray
                Write-Metric "Refresh" ("Every {0} seconds" -f $RefreshSeconds) DarkGray
            } elseif ($State.status -eq "complete") {
                Write-Section "PROGRESS"
                Write-Metric "Training" ("{0}  100.0%" -f (Format-ProgressBar 1.0 36 1.0)) Green
                Write-Metric "Time remaining" "00:00:00" Cyan
            }
        } catch {
            Write-Section "STATUS"
            Write-Metric "Dashboard" "Progress file is being updated; retrying..." Yellow
        }
    } else {
        Write-Section "STATUS"
        Write-Metric "Dashboard" "Waiting for the formal run to register..." Yellow
    }

    Write-Section "GPU HEALTH"
    if (Test-Path -LiteralPath $NvidiaSmi) {
        $GpuLine = & $NvidiaSmi --query-gpu=memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw --format=csv,noheader,nounits 2>$null
        $GpuParts = @([string]$GpuLine -split "," | ForEach-Object { $_.Trim() })
        try {
            $Invariant = [System.Globalization.CultureInfo]::InvariantCulture
            $MemoryTotalMiB = [double]::Parse($GpuParts[0], $Invariant)
            $MemoryUsedMiB = [double]::Parse($GpuParts[1], $Invariant)
            $MemoryFreeMiB = [double]::Parse($GpuParts[2], $Invariant)
            $GpuLoad = [double]::Parse($GpuParts[3], $Invariant)
            $GpuTemperature = [double]::Parse($GpuParts[4], $Invariant)
            $GpuPower = [double]::Parse($GpuParts[5], $Invariant)
            $MemoryFraction = $MemoryUsedMiB / [Math]::Max(1.0, $MemoryTotalMiB)
            $MemoryFreeGiB = $MemoryFreeMiB / 1024.0
            $MemoryColor = if ($MemoryFreeGiB -lt 7.0) { "Red" } elseif ($MemoryFreeGiB -lt 10.0) { "Yellow" } else { "Green" }
            $TemperatureColor = if ($GpuTemperature -ge 90.0) { "Red" } elseif ($GpuTemperature -ge 84.0) { "Yellow" } else { "Green" }
            Write-Metric "VRAM used" ("{0}  {1:N1} / {2:N1} GiB" -f (Format-ProgressBar $MemoryFraction 30 1.0), ($MemoryUsedMiB / 1024.0), ($MemoryTotalMiB / 1024.0)) $MemoryColor
            Write-Metric "VRAM free" ("{0:N1} GiB  (minimum target: 7.0 GiB)" -f $MemoryFreeGiB) $MemoryColor
            Write-Metric "GPU load" ("{0}  {1:N0}%" -f (Format-ProgressBar ($GpuLoad / 100.0) 30 1.0), $GpuLoad) Cyan
            Write-Metric "Temperature" ("{0:N0} C" -f $GpuTemperature) $TemperatureColor
            Write-Metric "Power" ("{0:N0} W" -f $GpuPower)
        } catch {
            Write-Metric "GPU" ([string]$GpuLine) Yellow
        }
    } else {
        Write-Metric "GPU" "nvidia-smi was not found" Yellow
    }

    Write-Section "LATEST COMPLETED EPOCH"
    if ($Rows.Count -gt 0) {
        $LatestRow = $Rows[-1]
        $WasValidated = if ([string]::IsNullOrWhiteSpace([string]$LatestRow.val_reference_score)) { "No" } else { "Yes" }
        Write-Metric "Epoch" ([string]$LatestRow.epoch) Cyan
        Write-Metric "Duration" (Format-Duration ([double]$LatestRow.seconds))
        Write-Metric "Patch size" ([string]$LatestRow.patch)
        Write-Metric "Full validation" $WasValidated
        if ($null -ne $State.adaptive_detail_multiplier) {
            Write-Metric "Detail multiplier" ("{0:N4}" -f [double]$State.adaptive_detail_multiplier)
        }
        if ($State.pareto_epochs) {
            Write-Metric "Saved candidates" ($State.pareto_epochs -join ", ") DarkGray
        }
    } elseif (Test-Path -LiteralPath $Stdout) {
        $LogInfo = Get-Item -LiteralPath $Stdout
        Write-Metric "Status" ("Waiting for first completed epoch; log updated at {0}" -f $LogInfo.LastWriteTime.ToString("HH:mm:ss")) Yellow
    }

    if ((Test-Path -LiteralPath $Stderr) -and (Get-Item -LiteralPath $Stderr).Length -gt 0) {
        Write-Section "LATEST WARNINGS"
        Get-Content -LiteralPath $Stderr -Tail 5
    }

    Write-Host ""
    Write-Rule "=" Cyan
    Write-Host "  Live percentage is a timing estimate; training recalibrates it after every epoch." -ForegroundColor DarkGray
    Write-Rule "=" Cyan

    if ($RefreshSeconds -gt 0) {
        Start-Sleep -Seconds $RefreshSeconds
    }
} while ($RefreshSeconds -gt 0)
