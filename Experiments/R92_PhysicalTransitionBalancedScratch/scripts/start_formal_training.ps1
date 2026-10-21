param(
    [string]$Python = "C:\Users\Rio\anaconda3\python.exe",
    [int]$Workers = 4
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot "launch_r92.py"
$LogDirectory = Join-Path $Root "runs\launcher_logs"
$Stdout = Join-Path $LogDirectory "formal_stdout.log"
$Stderr = Join-Path $LogDirectory "formal_stderr.log"
$PidRecord = Join-Path $LogDirectory "formal_process.json"

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

$Existing = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "launch_r92.py" -or $_.CommandLine -match "train_r92.py"
}
if ($Existing) {
    throw "An R92 launcher or trainer is already running."
}

$Arguments = @("-u", $Launcher, "--run-kind", "formal", "--device", "cuda:0", "--num-workers", "$Workers")
$Process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -WindowStyle Hidden -PassThru
@{
    pid = $Process.Id
    started_at = (Get-Date).ToString("o")
    stdout = $Stdout
    stderr = $Stderr
    root = $Root
} | ConvertTo-Json | Set-Content -LiteralPath $PidRecord -Encoding UTF8

Write-Host "R92 formal training started." -ForegroundColor Green
Write-Host "PID: $($Process.Id)"
Write-Host "Monitor: powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\monitor_training.ps1`""
