param(
    [ValidateSet('smoke','pilot','formal')][string]$Profile = 'formal',
    [ValidateSet('adapter_only','adapter_tail')][string]$Candidate = 'adapter_tail',
    [int]$Epochs = 30,
    [string]$RunSuffix = 'formal'
)

$ErrorActionPreference = 'Stop'
$ExperimentRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = 'C:\Users\Rio\anaconda3\python.exe'
$Launcher = Join-Path $ExperimentRoot 'scripts\launch_r83.py'
$LogDir = Join-Path $ExperimentRoot 'results\logs'
$LogPath = Join-Path $LogDir 'r83_training.log'
$ErrorPath = Join-Path $LogDir 'r83_training_error.log'
$PidPath = Join-Path $LogDir 'r83_training.pid'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$Arguments = @(
    $Launcher, '--profile', $Profile, '--candidate', $Candidate,
    '--num-epoch', $Epochs, '--run-suffix', $RunSuffix, '--build-data'
)
$Process = Start-Process -FilePath $PythonExe -ArgumentList $Arguments -WorkingDirectory $ExperimentRoot `
    -RedirectStandardOutput $LogPath -RedirectStandardError $ErrorPath -WindowStyle Hidden -PassThru
$Process.Id | Set-Content -LiteralPath $PidPath -Encoding ascii
Write-Host "R83 background training started. PID=$($Process.Id)" -ForegroundColor Cyan
Write-Host "Monitor: $ExperimentRoot\scripts\foreground_r83_monitor.ps1" -ForegroundColor Yellow
