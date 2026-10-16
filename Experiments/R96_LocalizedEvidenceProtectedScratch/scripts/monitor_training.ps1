[CmdletBinding()]
param(
    [int]$RefreshSeconds = 3,
    [switch]$Once,
    [switch]$NoClear,
    [int]$WidthOverride = 0,
    [int]$HeightOverride = 0
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ActivePath = Join-Path $Root "runs\active_run.json"
$RegistryPath = Join-Path $Root "runs\formal_run_registry.json"
$LauncherPath = Join-Path $Root "logs\launcher_state.json"
$DesignPath = Join-Path $Root "config\experiment_design.json"
$RecoveryPath = Join-Path $Root "config\interruption_recovery.json"
$DefaultStdout = Join-Path $Root "logs\formal_stdout.log"
$DefaultStderr = Join-Path $Root "logs\formal_stderr.log"
$Invariant = [System.Globalization.CultureInfo]::InvariantCulture

function Read-JsonSafe {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        return Get-Content -Raw -LiteralPath $Path -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Get-RowNumber {
    param([object]$Row, [string]$Name)
    if ($null -eq $Row) { return $null }
    $Property = $Row.PSObject.Properties[$Name]
    if ($null -eq $Property -or [string]::IsNullOrWhiteSpace([string]$Property.Value)) {
        return $null
    }
    try { return [double]::Parse([string]$Property.Value, $Invariant) } catch { return $null }
}

function Format-Duration {
    param([double]$Seconds)
    if ([double]::IsNaN($Seconds) -or [double]::IsInfinity($Seconds) -or $Seconds -lt 0) {
        return "estimating"
    }
    $Span = [TimeSpan]::FromSeconds([Math]::Round($Seconds))
    if ($Span.TotalDays -ge 1) {
        return ("{0}d {1:00}:{2:00}" -f [int][Math]::Floor($Span.TotalDays), $Span.Hours, $Span.Minutes)
    }
    return ("{0:00}:{1:00}:{2:00}" -f [int][Math]::Floor($Span.TotalHours), $Span.Minutes, $Span.Seconds)
}

function Update-Layout {
    if ($WidthOverride -gt 0) {
        $Width = $WidthOverride
    } else {
        try { $Width = $Host.UI.RawUI.WindowSize.Width - 1 } catch { $Width = 84 }
    }
    if ($HeightOverride -gt 0) {
        $Height = $HeightOverride
    } else {
        try { $Height = $Host.UI.RawUI.WindowSize.Height } catch { $Height = 26 }
    }
    $script:DashboardWidth = [Math]::Max(24, [Math]::Min(150, [int]$Width))
    $script:DashboardHeight = [Math]::Max(10, [int]$Height)
    $script:NarrowLayout = $script:DashboardWidth -lt 72
    $script:ShortLayout = $script:DashboardHeight -lt 24
}

function Limit-Text {
    param([string]$Text)
    if ($null -eq $Text) { return "" }
    if ($Text.Length -le $script:DashboardWidth) { return $Text }
    if ($script:DashboardWidth -le 3) { return $Text.Substring(0, $script:DashboardWidth) }
    return $Text.Substring(0, $script:DashboardWidth - 3) + "..."
}

function Write-DashboardLine {
    param(
        [string]$Text = "",
        [ConsoleColor]$Color = [ConsoleColor]::White
    )
    Write-Host (Limit-Text $Text) -ForegroundColor $Color
}

function Format-ProgressBar {
    param([double]$Fraction)
    $BarWidth = if ($script:NarrowLayout) {
        [Math]::Max(8, [Math]::Min(18, $script:DashboardWidth - 25))
    } else {
        [Math]::Max(16, [Math]::Min(30, $script:DashboardWidth - 48))
    }
    $Safe = [Math]::Max(0.0, [Math]::Min(0.995, $Fraction))
    $Filled = [Math]::Min($BarWidth, [Math]::Max(0, [int][Math]::Floor($Safe * $BarWidth)))
    return "[" + ("#" * $Filled) + ("." * ($BarWidth - $Filled)) + "]"
}

function Get-Ewma {
    param([object[]]$Values, [double]$Alpha = 0.70)
    $Usable = @($Values | Where-Object { $null -ne $_ } | ForEach-Object { [double]$_ })
    if ($Usable.Count -eq 0) { return $null }
    $Estimate = [double]$Usable[0]
    for ($Index = 1; $Index -lt $Usable.Count; $Index++) {
        $Estimate = $Alpha * [double]$Usable[$Index] + (1.0 - $Alpha) * $Estimate
    }
    return [double]$Estimate
}

$Design = Read-JsonSafe $DesignPath
$Recovery = Read-JsonSafe $RecoveryPath

function Get-PhaseForEpoch {
    param([int]$Epoch)
    if ($null -eq $Design) { return $null }
    return @($Design.training.phases | Where-Object {
        $Epoch -ge [int]$_.epoch_start -and $Epoch -le [int]$_.epoch_end
    }) | Select-Object -First 1
}

function Get-StageForEpoch {
    param([int]$Epoch)
    if ($null -eq $Design) { return $null }
    return @($Design.training.patch_schedule | Where-Object {
        $Epoch -ge [int]$_.epoch_start -and $Epoch -le [int]$_.epoch_end
    }) | Select-Object -First 1
}

function Get-PhaseShortName {
    param([string]$Name)
    switch ($Name) {
        "controls_and_geometry" { return "controls" }
        "private_causal_branch_targets" { return "private branches" }
        "teacher_to_predicted_causal_cascade" { return "causal handoff" }
        "fully_predicted_measurement_training" { return "full measurement" }
        "large_context_low_rate_consolidation" { return "large context" }
        default { return $Name }
    }
}

function Get-PhaseWeight {
    param([string]$Name)
    switch ($Name) {
        "controls_and_geometry" { return 0.72 }
        "private_causal_branch_targets" { return 1.00 }
        "teacher_to_predicted_causal_cascade" { return 1.30 }
        "fully_predicted_measurement_training" { return 2.20 }
        "large_context_low_rate_consolidation" { return 2.20 }
        default { return 1.00 }
    }
}

function Test-ValidationEpoch {
    param([int]$Epoch, [int]$PlannedEpochs)
    $Every = if ($null -ne $Recovery -and $null -ne $Recovery.online_validation_every_epochs) {
        [Math]::Max(1, [int]$Recovery.online_validation_every_epochs)
    } elseif ($null -ne $Design) {
        [Math]::Max(1, [int]$Design.training.validation_every_epochs)
    } else {
        2
    }
    return ($Epoch -eq 1) -or ($Epoch % $Every -eq 0) -or ($Epoch -eq $PlannedEpochs)
}

function Get-TrainingRows {
    param([object]$State)
    $Paths = @()
    if ($null -ne $State -and $State.training_log_segments) {
        $Paths += @($State.training_log_segments)
    } elseif ($null -ne $State -and $State.run_id) {
        $RecordDirectory = Join-Path $Root ("runs\training_" + [string]$State.run_id)
        $Paths += @(Get-ChildItem -LiteralPath $RecordDirectory -Filter "training_log*.csv" -ErrorAction SilentlyContinue |
            Sort-Object Name | ForEach-Object { $_.FullName })
    }
    $ByEpoch = @{}
    foreach ($Path in $Paths) {
        if (-not (Test-Path -LiteralPath ([string]$Path))) { continue }
        try {
            foreach ($Row in @(Import-Csv -LiteralPath ([string]$Path))) {
                $EpochValue = Get-RowNumber $Row "epoch"
                if ($null -ne $EpochValue) { $ByEpoch[[int]$EpochValue] = $Row }
            }
        } catch {
        }
    }
    return @($ByEpoch.GetEnumerator() | Sort-Object { [int]$_.Key } | ForEach-Object { $_.Value })
}

function Get-TrainingEstimateSeconds {
    param([int]$Epoch, [object[]]$Rows)
    $Phase = Get-PhaseForEpoch $Epoch
    $Stage = Get-StageForEpoch $Epoch
    $PhaseName = if ($null -ne $Phase) { [string]$Phase.name } else { "unknown" }
    $Patch = if ($null -ne $Stage) { [int]$Stage.patch_size } else { 768 }

    $ExactValues = @()
    foreach ($Row in @($Rows | Where-Object {
        [string]$_.phase -eq $PhaseName -and [int]$_.patch -eq $Patch
    })) {
        $TrainSeconds = Get-RowNumber $Row "train_seconds"
        $ValidationSeconds = Get-RowNumber $Row "validation_seconds"
        if ($null -ne $TrainSeconds -and $TrainSeconds -gt 0) {
            $ExactValues += $TrainSeconds
        } elseif (($null -eq $ValidationSeconds -or $ValidationSeconds -le 0) -and (Get-RowNumber $Row "seconds") -gt 0) {
            $ExactValues += (Get-RowNumber $Row "seconds")
        }
    }
    if ($ExactValues.Count -gt 0) {
        return [pscustomobject]@{
            Seconds = [double](Get-Ewma $ExactValues)
            Projected = $false
            SampleCount = $ExactValues.Count
            Patch = $Patch
            PhaseName = $PhaseName
        }
    }

    $MeasuredRows = @($Rows | Where-Object { (Get-RowNumber $_ "seconds") -gt 0 })
    if ($MeasuredRows.Count -gt 0) {
        $Source = $MeasuredRows[-1]
        $SourcePatch = [Math]::Max(1, [int](Get-RowNumber $Source "patch"))
        $SourcePhase = [string]$Source.phase
        $SourceSeconds = Get-RowNumber $Source "train_seconds"
        if ($null -eq $SourceSeconds -or $SourceSeconds -le 0) {
            $SourceSeconds = Get-RowNumber $Source "seconds"
        }
        $PatchScale = [Math]::Pow($Patch / [double]$SourcePatch, 2.0)
        $PhaseScale = (Get-PhaseWeight $PhaseName) / [Math]::Max(0.1, (Get-PhaseWeight $SourcePhase))
        return [pscustomobject]@{
            Seconds = [Math]::Max(30.0, [double]$SourceSeconds * $PatchScale * $PhaseScale)
            Projected = $true
            SampleCount = 0
            Patch = $Patch
            PhaseName = $PhaseName
        }
    }
    return [pscustomobject]@{
        Seconds = 260.0 * [Math]::Pow($Patch / 768.0, 2.0) * (Get-PhaseWeight $PhaseName)
        Projected = $true
        SampleCount = 0
        Patch = $Patch
        PhaseName = $PhaseName
    }
}

function Get-ValidationEstimateSeconds {
    param([int]$Patch, [object[]]$Rows)
    $Exact = @($Rows | Where-Object { [int]$_.patch -eq $Patch } | ForEach-Object {
        $Value = Get-RowNumber $_ "validation_seconds"
        if ($null -ne $Value -and $Value -gt 0) { $Value }
    })
    if ($Exact.Count -gt 0) { return [double](Get-Ewma $Exact) }
    $Measured = @($Rows | ForEach-Object {
        $Value = Get-RowNumber $_ "validation_seconds"
        if ($null -ne $Value -and $Value -gt 0) {
            [pscustomobject]@{ Seconds = $Value; Patch = [int]$_.patch }
        }
    })
    if ($Measured.Count -gt 0) {
        $Source = $Measured[-1]
        return [double]$Source.Seconds * [Math]::Pow($Patch / [double][Math]::Max(1, $Source.Patch), 2.0)
    }
    return 45.0 * [Math]::Pow($Patch / 768.0, 2.0)
}

function Get-EpochEstimate {
    param([int]$Epoch, [int]$PlannedEpochs, [object[]]$Rows)
    $Training = Get-TrainingEstimateSeconds $Epoch $Rows
    $NeedsValidation = Test-ValidationEpoch $Epoch $PlannedEpochs
    $ValidationSeconds = if ($NeedsValidation) { Get-ValidationEstimateSeconds $Training.Patch $Rows } else { 0.0 }
    $Estimate = [double]$Training.Seconds + [double]$ValidationSeconds
    $UncertaintyFraction = if ($Training.Projected) { 0.32 } elseif ($Training.SampleCount -lt 3) { 0.16 } else { 0.10 }
    return [pscustomobject]@{
        Seconds = $Estimate
        TrainingSeconds = [double]$Training.Seconds
        ValidationSeconds = [double]$ValidationSeconds
        Uncertainty = [Math]::Max(18.0, $UncertaintyFraction * $Estimate)
        Projected = [bool]$Training.Projected
        NeedsValidation = $NeedsValidation
        Patch = [int]$Training.Patch
        PhaseName = [string]$Training.PhaseName
    }
}

function Resolve-NvidiaSmi {
    $Command = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
    if ($null -ne $Command) { return $Command.Source }
    $Known = "C:\Windows\System32\DriverStore\FileRepository\nv_dispwi.inf_amd64_9d6b008f0a7ed9e5\nvidia-smi.exe"
    if (Test-Path -LiteralPath $Known) { return $Known }
    try {
        return Get-ChildItem -LiteralPath "C:\Windows\System32\DriverStore\FileRepository" -Filter "nvidia-smi.exe" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
    } catch {
        return $null
    }
}

$NvidiaSmi = Resolve-NvidiaSmi

do {
    Update-Layout
    if (-not $NoClear -and -not $Once) { Clear-Host }
    $Now = Get-Date
    $State = Read-JsonSafe $ActivePath
    $Registry = Read-JsonSafe $RegistryPath
    $Launcher = Read-JsonSafe $LauncherPath
    $Rows = @(Get-TrainingRows $State)

    $Status = if ($null -ne $State) { ([string]$State.status).ToUpperInvariant() } else { "WAITING" }
    $Completed = if ($null -ne $State) { [int]$State.completed_epoch } else { 0 }
    $Planned = if ($null -ne $State -and [int]$State.planned_epochs -gt 0) { [int]$State.planned_epochs } elseif ($null -ne $Design) { [int]$Design.training.planned_epochs } else { 0 }
    $StatusColor = if ($Status -in @("ACTIVE", "CONTINUING")) { "Green" } elseif ($Status -eq "COMPLETE") { "Cyan" } elseif ($Status -eq "WAITING") { "Yellow" } else { "Red" }
    try { $Host.UI.RawUI.WindowTitle = "R96 Monitor | $Status | E$Completed/$Planned" } catch {}

    Write-DashboardLine ("R96  {0}  E{1}/{2}  {3}" -f $Status, $Completed, $Planned, $Now.ToString("MM-dd HH:mm:ss")) $StatusColor

    $CurrentEpoch = 0
    $CurrentInfo = $null
    $HasProjection = $false
    if ($null -ne $State -and $Status -in @("ACTIVE", "CONTINUING") -and $Completed -lt $Planned) {
        $CurrentEpoch = $Completed + 1
        $CurrentInfo = Get-EpochEstimate $CurrentEpoch $Planned $Rows
        $ActiveInfo = Get-Item -LiteralPath $ActivePath -ErrorAction SilentlyContinue
        $EpochStarted = if ($Completed -eq 0 -and $State.started_at) { [datetime]$State.started_at } elseif ($null -ne $ActiveInfo) { $ActiveInfo.LastWriteTime } else { $Now }
        $Elapsed = [Math]::Max(0.0, ($Now - $EpochStarted).TotalSeconds)
        $Fraction = if ($CurrentInfo.Seconds -gt 0) { [Math]::Min(0.995, $Elapsed / $CurrentInfo.Seconds) } else { 0.0 }
        $EpochLeft = [Math]::Max(0.0, $CurrentInfo.Seconds - $Elapsed)
        $LivePhase = if ($CurrentInfo.NeedsValidation -and $Elapsed -ge $CurrentInfo.TrainingSeconds) { "validation/save" } else { "training" }
        $ShortPhase = Get-PhaseShortName $CurrentInfo.PhaseName
        Write-DashboardLine ("NOW  E{0}  {1}  {2}px  {3}" -f $CurrentEpoch, $ShortPhase, $CurrentInfo.Patch, $LivePhase) Cyan
        if ($script:NarrowLayout) {
            Write-DashboardLine ("{0} {1,5:N1}%" -f (Format-ProgressBar $Fraction), (100.0 * $Fraction)) Green
            Write-DashboardLine ("EPOCH  elapsed {0}  left ~{1}" -f (Format-Duration $Elapsed), (Format-Duration $EpochLeft)) Green
        } else {
            Write-DashboardLine ("{0} {1,5:N1}%  elapsed {2}  left ~{3}" -f (Format-ProgressBar $Fraction), (100.0 * $Fraction), (Format-Duration $Elapsed), (Format-Duration $EpochLeft)) Green
        }

        $TotalRemaining = $EpochLeft
        $TotalVariance = $CurrentInfo.Uncertainty * $CurrentInfo.Uncertainty
        $HasProjection = [bool]$CurrentInfo.Projected
        for ($FutureEpoch = $CurrentEpoch + 1; $FutureEpoch -le $Planned; $FutureEpoch++) {
            $Future = Get-EpochEstimate $FutureEpoch $Planned $Rows
            $TotalRemaining += $Future.Seconds
            $TotalVariance += $Future.Uncertainty * $Future.Uncertainty
            $HasProjection = $HasProjection -or $Future.Projected
        }
        $Systematic = if ($HasProjection) { 0.15 * $TotalRemaining } else { 0.05 * $TotalRemaining }
        $Band = [Math]::Max(1.65 * [Math]::Sqrt($TotalVariance), $Systematic)
        $Low = [Math]::Max(0.0, $TotalRemaining - $Band)
        $High = $TotalRemaining + $Band
        $Finish = $Now.AddSeconds($TotalRemaining)
        if ($script:NarrowLayout) {
            Write-DashboardLine ("RUN  left ~{0}  ETA {1}" -f (Format-Duration $TotalRemaining), $Finish.ToString("MM-dd HH:mm")) Yellow
        } else {
            Write-DashboardLine ("RUN  left ~{0}  range {1}-{2}  ETA {3}" -f (Format-Duration $TotalRemaining), (Format-Duration $Low), (Format-Duration $High), $Finish.ToString("MM-dd HH:mm")) Yellow
        }
    } elseif ($Status -eq "COMPLETE") {
        Write-DashboardLine ("[##################] 100.0%  training complete") Green
    } elseif ($null -eq $State) {
        Write-DashboardLine "Waiting for the formal progress file..." Yellow
    }

    if ($null -ne $NvidiaSmi -and (Test-Path -LiteralPath $NvidiaSmi)) {
        try {
            $GpuLine = & $NvidiaSmi --query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu,power.draw --format=csv,noheader,nounits 2>$null | Select-Object -First 1
            $Parts = @([string]$GpuLine -split "," | ForEach-Object { $_.Trim() })
            $GpuLoad = [double]::Parse($Parts[0], $Invariant)
            $UsedGiB = [double]::Parse($Parts[1], $Invariant) / 1024.0
            $FreeGiB = [double]::Parse($Parts[2], $Invariant) / 1024.0
            $Temperature = [double]::Parse($Parts[3], $Invariant)
            $Power = [double]::Parse($Parts[4], $Invariant)
            $GpuColor = if ($Temperature -ge 93 -or $FreeGiB -lt 1.0) { "Red" } elseif ($Temperature -ge 84 -or $FreeGiB -lt 3.0) { "Yellow" } else { "Green" }
            if ($script:NarrowLayout) {
                Write-DashboardLine ("GPU  {0:N0}%  VRAM {1:N1}G used / {2:N1}G free" -f $GpuLoad, $UsedGiB, $FreeGiB) $GpuColor
                Write-DashboardLine ("TEMP {0:N0}C  POWER {1:N0}W" -f $Temperature, $Power) $GpuColor
            } else {
                Write-DashboardLine ("GPU  {0:N0}%  VRAM {1:N1}G used / {2:N1}G free  {3:N0}C  {4:N0}W" -f $GpuLoad, $UsedGiB, $FreeGiB, $Temperature, $Power) $GpuColor
            }
        } catch {
            Write-DashboardLine ("GPU  query unavailable: " + [string]$GpuLine) Yellow
        }
    } else {
        Write-DashboardLine "GPU  nvidia-smi not found" Yellow
    }

    if ($Rows.Count -gt 0) {
        $Latest = $Rows[-1]
        $LastSeconds = Get-RowNumber $Latest "seconds"
        $LastTotal = Get-RowNumber $Latest "train_total"
        $LastSeparation = Get-RowNumber $Latest "train_need_separation"
        if ($script:NarrowLayout) {
            Write-DashboardLine ("LAST E{0}  {1}  loss {2:N4}  sep {3:+0.0000;-0.0000;0.0000}" -f [int]$Latest.epoch, (Format-Duration $LastSeconds), $LastTotal, $LastSeparation) White
        } else {
            Write-DashboardLine ("LAST E{0}  {1}  loss {2:N4}  separation {3:+0.0000;-0.0000;0.0000}" -f [int]$Latest.epoch, (Format-Duration $LastSeconds), $LastTotal, $LastSeparation) White
        }

        $ValidatedRows = @($Rows | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.val_need_separation) })
        if ($ValidatedRows.Count -gt 0) {
            $Validation = $ValidatedRows[-1]
            $Detail = Get-RowNumber $Validation "val_detail_axis"
            $Contour = Get-RowNumber $Validation "val_contour_axis"
            $Identity = Get-RowNumber $Validation "val_identity_axis"
            $Motion = Get-RowNumber $Validation "val_motion_axis"
            if ($script:NarrowLayout) {
                Write-DashboardLine ("VAL E{0}  detail {1:N4}  contour {2:N4}" -f [int]$Validation.epoch, $Detail, $Contour) Magenta
                Write-DashboardLine ("VAL      identity {0:N3}  motion {1:N4}" -f $Identity, $Motion) Magenta
            } else {
                Write-DashboardLine ("VAL  E{0}  detail {1:N4}  contour {2:N4}  identity {3:N3}  motion {4:N4}" -f [int]$Validation.epoch, $Detail, $Contour, $Identity, $Motion) Magenta
            }
        }
    } else {
        Write-DashboardLine "LAST  no completed epoch yet" DarkGray
    }

    $LauncherPid = if ($null -ne $Launcher -and $Launcher.process_id) { [int]$Launcher.process_id } else { 0 }
    $LauncherAlive = $false
    $Trainer = $null
    if ($LauncherPid -gt 0) {
        $LauncherAlive = $null -ne (Get-Process -Id $LauncherPid -ErrorAction SilentlyContinue)
        if ($LauncherAlive) {
            try {
                $Trainer = Get-CimInstance Win32_Process -Filter ("ParentProcessId = {0}" -f $LauncherPid) -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -match "python" -and $_.CommandLine -like "*train_r96.py*" } | Select-Object -First 1
            } catch {
                $Trainer = $null
            }
        }
    }
    $StdoutPath = if ($null -ne $Launcher -and $Launcher.stdout) { [string]$Launcher.stdout } else { $DefaultStdout }
    $StderrPath = if ($null -ne $Launcher -and $Launcher.stderr) { [string]$Launcher.stderr } else { $DefaultStderr }
    $StderrBytes = if (Test-Path -LiteralPath $StderrPath) { (Get-Item -LiteralPath $StderrPath).Length } else { 0 }
    $CheckpointPath = if ($null -ne $State -and $State.weight_dir) { Join-Path ([string]$State.weight_dir) "latest.pth.tar" } else { $null }
    $CheckpointOk = $null -ne $CheckpointPath -and (Test-Path -LiteralPath $CheckpointPath)
    $HealthOk = (($Status -eq "COMPLETE") -or ($LauncherAlive -and $null -ne $Trainer)) -and $StderrBytes -eq 0 -and (($null -eq $State) -or $CheckpointOk)
    $TrainerText = if ($null -ne $Trainer) { "trainer OK pid $($Trainer.ProcessId)" } elseif ($Status -eq "COMPLETE") { "trainer finished" } else { "trainer NOT FOUND" }
    $ErrorText = if ($StderrBytes -eq 0) { "errors clear" } else { "stderr $StderrBytes bytes" }
    $CheckpointText = if ($CheckpointOk) { "checkpoint E$Completed" } else { "checkpoint missing" }
    $HealthColor = if ($HealthOk) { "Green" } else { "Red" }
    if ($script:NarrowLayout) {
        Write-DashboardLine ("HEALTH  " + $TrainerText) $HealthColor
        Write-DashboardLine ("CHECK   {0} | {1}" -f $ErrorText, $CheckpointText) $HealthColor
    } else {
        Write-DashboardLine ("HEALTH  {0}  | {1} | {2}" -f $TrainerText, $ErrorText, $CheckpointText) $HealthColor
    }

    if (-not $script:ShortLayout) {
        $ExecutionText = if ($null -ne $State -and $State.background_prefetch) { "8 CPU threads + prefetch" } else { "standard loader" }
        $EstimateQuality = if ($null -ne $CurrentInfo -and $CurrentInfo.Projected) {
            "current + future projected"
        } elseif ($HasProjection) {
            "current measured; future projected"
        } else {
            "measured by phase"
        }
        Write-DashboardLine ("MODE  {0}  | ETA: {1} | refresh {2}s" -f $ExecutionText, $EstimateQuality, $RefreshSeconds) DarkGray
        Write-DashboardLine "Ctrl+C closes this monitor only; training keeps running." DarkGray
    }

    if ($StderrBytes -gt 0 -and -not $script:ShortLayout) {
        Write-DashboardLine "WARNING  latest stderr:" Red
        foreach ($Line in @(Get-Content -LiteralPath $StderrPath -Tail 2 -ErrorAction SilentlyContinue)) {
            Write-DashboardLine ("  " + [string]$Line) Red
        }
    }

    if ($Once -or $RefreshSeconds -le 0) { break }
    Start-Sleep -Seconds ([Math]::Max(1, $RefreshSeconds))
} while ($true)
