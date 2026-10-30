param(
    [int]$IntervalSeconds = 10,
    [int]$BarWidth = 42,
    [switch]$Once,
    [switch]$Plain
)

$ErrorActionPreference = "SilentlyContinue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentDir = Split-Path -Parent $ScriptDir
$LogRoot = Join-Path $ExperimentDir "logs"
$ProjectRoot = (Resolve-Path (Join-Path $ExperimentDir "..\..\..")).Path
$ProgressRoot = Join-Path $ProjectRoot "LabSystem_MOSR\Traing_Progress"

function Get-LatestProcessRecord {
    $records = Get-ChildItem -LiteralPath $LogRoot -Filter "v41_standalone_*_process.json" -File |
        Sort-Object LastWriteTime -Descending

    foreach ($record in $records) {
        try {
            return Get-Content -LiteralPath $record.FullName -Raw | ConvertFrom-Json
        } catch {
        }
    }
    return $null
}

function Get-ProgressDirectory {
    param([object]$Info)

    if ($null -eq $Info) {
        return $null
    }

    $stdout = [string]$Info.stdout
    if ($stdout -and (Test-Path -LiteralPath $stdout)) {
        $lines = Get-Content -LiteralPath $stdout -Tail 200
        for ($i = $lines.Count - 1; $i -ge 0; $i--) {
            $match = [regex]::Match([string]$lines[$i], "^\[RUN\] progress_dir=(.+)$")
            if ($match.Success) {
                $candidate = $match.Groups[1].Value.Trim()
                if (Test-Path -LiteralPath $candidate) {
                    return $candidate
                }
            }
        }
    }

    if (-not (Test-Path -LiteralPath $ProgressRoot)) {
        return $null
    }

    $dirs = Get-ChildItem -LiteralPath $ProgressRoot -Directory -Filter "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_v41_standalone_long*" |
        Sort-Object LastWriteTime -Descending
    $suffix = [string]$Info.run_suffix
    if ($suffix) {
        $matched = $dirs | Where-Object { $_.Name -like "*$suffix*" } | Select-Object -First 1
        if ($matched) {
            return $matched.FullName
        }
    }

    $latest = $dirs | Select-Object -First 1
    if ($latest) {
        return $latest.FullName
    }
    return $null
}

function Get-MaxEpochFromText {
    param(
        [string]$Path,
        [string]$Pattern
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }

    $maxEpoch = 0
    foreach ($line in (Get-Content -LiteralPath $Path)) {
        $match = [regex]::Match([string]$line, $Pattern)
        if ($match.Success) {
            $epoch = [int]$match.Groups[1].Value
            if ($epoch -gt $maxEpoch) {
                $maxEpoch = $epoch
            }
        }
    }
    return $maxEpoch
}

function Get-MaxEpochFromFiles {
    param([string]$ProgressDir)

    if (-not $ProgressDir -or -not (Test-Path -LiteralPath $ProgressDir)) {
        return 0
    }

    $maxEpoch = 0
    $scanDirs = @($ProgressDir, (Join-Path $ProgressDir "weights"))
    $patterns = @(
        "monitor_epoch_(\d+)_",
        "^epoch_(\d+)",
        "_epoch(\d+)_"
    )

    foreach ($dir in $scanDirs) {
        if (-not (Test-Path -LiteralPath $dir)) {
            continue
        }
        foreach ($file in (Get-ChildItem -LiteralPath $dir -File)) {
            foreach ($pattern in $patterns) {
                $match = [regex]::Match($file.Name, $pattern)
                if ($match.Success) {
                    $epoch = [int]$match.Groups[1].Value
                    if ($epoch -gt $maxEpoch) {
                        $maxEpoch = $epoch
                    }
                }
            }
        }
    }
    return $maxEpoch
}

function Get-CurrentEpoch {
    param([string]$ProgressDir)

    if (-not $ProgressDir -or -not (Test-Path -LiteralPath $ProgressDir)) {
        return 0
    }

    $candidates = @()
    $attribLog = Join-Path $ProgressDir "attribution_log.txt"
    $candidates += Get-MaxEpochFromText -Path $attribLog -Pattern "\[ATTRIB\]\[E(\d+)\]"
    $candidates += Get-MaxEpochFromFiles -ProgressDir $ProgressDir

    return ($candidates | Measure-Object -Maximum).Maximum
}

function Get-EpochProgressState {
    $info = Get-LatestProcessRecord
    $totalEpochs = 0
    if ($info -and $info.epochs) {
        $totalEpochs = [int]$info.epochs
    }
    if ($totalEpochs -le 0) {
        $totalEpochs = 16
    }

    $progressDir = Get-ProgressDirectory -Info $info
    $epoch = [int](Get-CurrentEpoch -ProgressDir $progressDir)
    if ($epoch -lt 0) {
        $epoch = 0
    }
    if ($epoch -gt $totalEpochs) {
        $epoch = $totalEpochs
    }

    $percent = [math]::Round(($epoch / $totalEpochs) * 100.0, 1)
    $filled = [math]::Floor(($percent / 100.0) * $BarWidth)
    if ($filled -lt 0) { $filled = 0 }
    if ($filled -gt $BarWidth) { $filled = $BarWidth }

    $bar = "[" + ("#" * $filled) + ("-" * ($BarWidth - $filled)) + "]"

    return [pscustomobject]@{
        Epoch = $epoch
        TotalEpochs = $totalEpochs
        Percent = $percent
        Bar = $bar
    }
}

function Write-EpochProgress {
    param([switch]$Plain)

    $state = Get-EpochProgressState
    $status = "Epoch {0}/{1} ({2:N1}%)" -f $state.Epoch, $state.TotalEpochs, $state.Percent

    if ($Plain) {
        Write-Output ("Epoch {0}/{1}" -f $state.Epoch, $state.TotalEpochs)
        Write-Output ("{0} {1,5:N1}%" -f $state.Bar, $state.Percent)
        return
    }

    if ($state.Percent -ge 100) {
        Write-Progress -Id 1 -Activity "V41-Standalone training" -Status $status -PercentComplete 100 -Completed
        return
    }

    Write-Progress -Id 1 -Activity "V41-Standalone training" -Status $status -PercentComplete $state.Percent
}

while ($true) {
    if ($Plain -and -not $Once) {
        try {
            [Console]::Clear()
        } catch {
        }
    }

    Write-EpochProgress -Plain:$Plain

    if ($Once) {
        break
    }

    Start-Sleep -Seconds $IntervalSeconds
}
