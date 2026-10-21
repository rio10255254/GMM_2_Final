param(
    [string]$Device = "cuda:0",
    [int]$Seed = 752031,
    [int]$Epochs = 100,
    [switch]$SkipPreparation
)

$ErrorActionPreference = "Stop"
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Experiment = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot "launch_r75v3.py"
$DatasetBuilder = Join-Path $PSScriptRoot "r75v3_dataset.py"
$LiveValidationBuilder = Join-Path $Experiment "tools\prepare_live_validation.py"
$LogDir = Join-Path $Experiment "runs\launcher_logs"
$ActiveRun = Join-Path $LogDir "active_formal_run.json"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "^python" -and
        $_.CommandLine -match "launch_r75v3\.py" -and
        $_.CommandLine -match "--profile formal"
    }
if ($existing) {
    $ids = ($existing | Select-Object -ExpandProperty ProcessId) -join ", "
    throw "An R75-v3 formal training process is already running. PID: $ids"
}

if (-not $SkipPreparation) {
    & $Python $LiveValidationBuilder
    if ($LASTEXITCODE -ne 0) { throw "R75-v3 live-validation preparation failed." }

    & $Python $DatasetBuilder --profile formal
    if ($LASTEXITCODE -ne 0) { throw "R75-v3 formal dataset preparation failed." }

    & $Python $Launcher --profile formal --dry-run --device $Device --seed $Seed --num-epoch $Epochs --no-amp
    if ($LASTEXITCODE -ne 0) { throw "R75-v3 pre-training audit failed." }
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutLog = Join-Path $LogDir "r75v3_formal_e${Epochs}_${Stamp}.out.log"
$ErrLog = Join-Path $LogDir "r75v3_formal_e${Epochs}_${Stamp}.err.log"
$Arguments = @(
    "-u",
    $Launcher,
    "--profile", "formal",
    "--device", $Device,
    "--seed", "$Seed",
    "--num-epoch", "$Epochs",
    "--no-amp",
    "--run-suffix", "dense_multiscale_e${Epochs}"
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
    throw "R75-v3 training exited immediately with code $($Process.ExitCode). $($stderr -join ' ')"
}

$Metadata = [ordered]@{
    experiment_id = "R79_R75v3_DenseMicroscopyScratchGeneralization"
    status = "running"
    process_id = $Process.Id
    started_at = (Get-Date).ToString("o")
    device = $Device
    seed = $Seed
    epochs = $Epochs
    amp_enabled = $false
    live_validation_every_n_epochs = 5
    stdout_log = $OutLog
    stderr_log = $ErrLog
    launcher = $Launcher
}
$Metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ActiveRun -Encoding UTF8
$Metadata | ConvertTo-Json -Depth 4
