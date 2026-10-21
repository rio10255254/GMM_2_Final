$ErrorActionPreference = "Stop"

$RepoRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence"
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Launcher = Join-Path $RepoRoot "LabSystem_MOSR\Experiments\R56_LabelCoreRepairTraining\scripts\launch_r56.py"
$DataRoot = Join-Path $RepoRoot "LabSystem_MOSR\Training_Data\r56_label_core_repair\r53_realistic_dataset_calibration"
$LogDir = Join-Path $RepoRoot "LabSystem_MOSR\Experiments\R56_LabelCoreRepairTraining\results\formal_training_logs"
$RunSuffix = "formal_label_core_repair_e050_b016_w04_nophys"
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Stdout = Join-Path $LogDir "r56_${RunSuffix}_${Stamp}_stdout.log"
$Stderr = Join-Path $LogDir "r56_${RunSuffix}_${Stamp}_stderr.log"
$Pointer = Join-Path $LogDir "latest_formal_training_log.txt"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ArgsList = @(
  "-u",
  $Launcher,
  "--candidate", "r56_label_core_repair_r53_scratch",
  "--data-root", $DataRoot,
  "--num-epoch", "50",
  "--batch-size", "16",
  "--val-batch-size", "4",
  "--num-workers", "4",
  "--seq-batch-size", "4",
  "--run-suffix", $RunSuffix
)

Set-Content -Path $Pointer -Encoding UTF8 -Value @(
  "started_at=$Stamp",
  "launcher=$Launcher",
  "data_root=$DataRoot",
  "stdout=$Stdout",
  "stderr=$Stderr"
)

$Process = Start-Process -FilePath $Python -ArgumentList $ArgsList -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -PassThru -WindowStyle Hidden
Add-Content -Path $Pointer -Encoding UTF8 -Value "pid=$($Process.Id)"
Write-Host "Started R56 formal training. PID=$($Process.Id)"
Write-Host "stdout=$Stdout"
Write-Host "stderr=$Stderr"
