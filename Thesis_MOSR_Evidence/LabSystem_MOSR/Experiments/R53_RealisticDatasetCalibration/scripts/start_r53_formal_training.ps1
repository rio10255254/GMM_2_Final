$ErrorActionPreference = "Stop"

$ThesisRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence"
$ExperimentRoot = Join-Path $ThesisRoot "LabSystem_MOSR\Experiments\R53_RealisticDatasetCalibration"
$Launcher = Join-Path $ExperimentRoot "scripts\launch_r53.py"
$PythonExe = "C:\Users\Rio\anaconda3\python.exe"
$LogDir = Join-Path $ExperimentRoot "results\formal_training_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "r53_formal_b016_w04_nophys_e100_$Stamp.log"
$LatestPath = Join-Path $LogDir "latest_formal_training_log.txt"
Set-Content -LiteralPath $LatestPath -Value $LogPath -Encoding UTF8

Set-Location $ThesisRoot
$env:PYTHONUNBUFFERED = "1"
& $PythonExe -u $Launcher `
  --candidate r53_realistic_calibrated_scratch `
  --num-epoch 100 `
  --batch-size 16 `
  --val-batch-size 4 `
  --num-workers 4 `
  --seq-batch-size 4 `
  --run-suffix formal_b016_w04_nophys_e100 `
  2>&1 | Tee-Object -FilePath $LogPath
