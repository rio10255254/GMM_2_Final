param(
    [string]$Device = "cuda:0",
    [int]$Seed = 752031,
    [int]$Epochs = 100,
    [switch]$SkipPreparation
)

$ErrorActionPreference = "Stop"
$Python = python
$Experiment = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot "launch_r75v2.py"
$DatasetBuilder = Join-Path $PSScriptRoot "r75v2_dataset.py"
$LogDir = Join-Path $Experiment "runs\launcher_logs"
$ActiveRun = Join-Path $LogDir "active_formal_run.json"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "^python" -and
        $_.CommandLine -match "launch_r75v2\.py" -and
        $_.CommandLine -match "--profile formal"
    }
if ($existing) {
    $ids = ($existing | Select-Object -ExpandProperty ProcessId) -join ", "
    throw "An R75-v2 formal training process is already running. PID: $ids"
}

if (-not $SkipPreparation) {
    & $Python $DatasetBuilder --profile formal
    if ($LASTEXITCODE -ne 0) { throw "R75-v2 formal dataset preparation failed." }

    & $Python $Launcher --profile formal --dry-run --device $Device --seed $Seed --num-epoch $Epochs --no-amp
    if ($LASTEXITCODE -ne 0) { throw "R75-v2 pre-training audit failed." }
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutLog = Join-Path $LogDir "r75v2_formal_e${Epochs}_${Stamp}.out.log"
$ErrLog = Join-Path $LogDir "r75v2_formal_e${Epochs}_${Stamp}.err.log"
$Arguments = @(
    "-u",
    $Launcher,
    "--profile", "formal",
    "--device", $Device,
    "--seed", "$Seed",
    "--num-epoch", "$Epochs",
    "--no-amp",
    "--run-suffix", "diverse_data_e${Epochs}"
)

$Process = Start-Process `
    -FilePath $Python `
    -ArgumentList $Arguments `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 2
if ($Process.HasExited) {
    $stderr = if (Test-Path -LiteralPath $ErrLog) { Get-Content -LiteralPath $ErrLog -Tail 30 } else { @() }
    throw "R75-v2 training exited immediately with code $($Process.ExitCode). $($stderr -join ' ')"
}

$Metadata = [ordered]@{
    experiment_id = "R75v2_R61ArchitectureScratchGeneralization"
    status = "running"
    process_id = $Process.Id
    started_at = (Get-Date).ToString("o")
    device = $Device
    seed = $Seed
    epochs = $Epochs
    amp_enabled = $false
    stdout_log = $OutLog
    stderr_log = $ErrLog
    launcher = $Launcher
}
$Metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ActiveRun -Encoding UTF8
$Metadata | ConvertTo-Json -Depth 4
