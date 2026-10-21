param(
    [double]$PollSec = 5,
    [int]$BatchSize = 8
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python).Source
$MonitorScript = Join-Path $PackageRoot "foreground_epoch_monitor.py"

& $Python $MonitorScript `
    --package-root $PackageRoot `
    --manifest (Join-Path $PackageRoot "CURRENT_FULL_TRAINING_RUN.json") `
    --poll-sec $PollSec `
    --batch-size $BatchSize
