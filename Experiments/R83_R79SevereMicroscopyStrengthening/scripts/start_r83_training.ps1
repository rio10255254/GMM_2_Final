param(
    [ValidateSet('smoke','pilot','formal')][string]$Profile = 'pilot',
    [ValidateSet('adapter_only','adapter_tail')][string]$Candidate = 'adapter_tail',
    [int]$Epochs = 4,
    [string]$RunSuffix = 'manual'
)

$ErrorActionPreference = 'Stop'
$ExperimentRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = 'C:\Users\Rio\anaconda3\python.exe'
$Launcher = Join-Path $ExperimentRoot 'scripts\launch_r83.py'

if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python not found: $PythonExe" }
if (-not (Test-Path -LiteralPath $Launcher)) { throw "Launcher not found: $Launcher" }

Write-Host "R83 training starts in this terminal." -ForegroundColor Cyan
Write-Host "Profile=$Profile Candidate=$Candidate Epochs=$Epochs" -ForegroundColor Yellow
& $PythonExe $Launcher --profile $Profile --candidate $Candidate --num-epoch $Epochs --run-suffix $RunSuffix --build-data
exit $LASTEXITCODE
