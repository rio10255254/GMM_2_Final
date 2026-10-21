$ErrorActionPreference = "Stop"
$Experiment = Split-Path -Parent $PSScriptRoot
$ActiveRun = Join-Path $Experiment "runs\launcher_logs\active_formal_run.json"

if (-not (Test-Path -LiteralPath $ActiveRun)) {
    [ordered]@{
        status = "not_started"
        active_run_file = $ActiveRun
    } | ConvertTo-Json
    exit 0
}

$Metadata = Get-Content -LiteralPath $ActiveRun -Raw | ConvertFrom-Json
$Process = Get-Process -Id ([int]$Metadata.process_id) -ErrorAction SilentlyContinue
$OutLog = [string]$Metadata.stdout_log
$ErrLog = [string]$Metadata.stderr_log
$LastEpochLine = $null
$TrainingComplete = $false
if (Test-Path -LiteralPath $OutLog) {
    $Tail = Get-Content -LiteralPath $OutLog -Tail 300
    $LastEpochLine = [string](@(
        $Tail |
            Where-Object { $_ -match "Epoch\s*\[?\d+" -or $_ -match "\[Epoch\s+\d+" } |
            ForEach-Object { [string]$_ }
    ) | Select-Object -Last 1)
    $TrainingComplete = [bool]($Tail | Where-Object { $_ -match '"training_complete"\s*:\s*true' })
}
$LiveCount = 0
$LatestLiveFile = $null
$LatestRun = Get-ChildItem -LiteralPath (Join-Path $Experiment "runs") -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "R75v3_scratch_formal" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($LatestRun) {
    $LiveFiles = @(
        Get-ChildItem -LiteralPath (Join-Path $LatestRun.FullName "live_validation") -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^epoch_\d+\.bmp$" }
    )
    $LiveCount = $LiveFiles.Count
    $LatestLiveFile = $LiveFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

[ordered]@{
    status = if ($Process) { "running" } elseif ($TrainingComplete) { "complete" } else { "stopped_or_failed" }
    process_id = [int]$Metadata.process_id
    started_at = [string]$Metadata.started_at
    process_running = [bool]$Process
    last_epoch_line = $LastEpochLine
    live_validation_file_count = $LiveCount
    latest_live_validation_file = if ($LatestLiveFile) { [string]$LatestLiveFile.FullName } else { $null }
    live_validation_counts = if ($LatestRun) {
        [ordered]@{
            five_x = @($LiveFiles | Where-Object { $_.Directory.Name -eq "5x_dense_raw" }).Count
            twenty_x = @($LiveFiles | Where-Object { $_.Directory.Name -eq "20x_mixed_raw" }).Count
            fifty_x = @($LiveFiles | Where-Object { $_.Directory.Name -eq "50x_array_raw" }).Count
        }
    } else { $null }
    latest_run_directory = if ($LatestRun) { $LatestRun.FullName } else { $null }
    stdout_log = $OutLog
    stderr_log = $ErrLog
    stderr_tail = if (Test-Path -LiteralPath $ErrLog) {
        @(Get-Content -LiteralPath $ErrLog -Tail 12 | ForEach-Object { [string]$_ })
    } else { @() }
} | ConvertTo-Json -Depth 5
