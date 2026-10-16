$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\Rio\anaconda3\python.exe'
$trainer = Join-Path $root 'training\train.py'
$lock = Join-Path $root 'runs\active_run.lock'
if (Test-Path -LiteralPath $lock) {
    throw ('An R116 run is already active: ' + (Get-Content -LiteralPath $lock -Raw))
}
$runId = 'r116_formal_scratch_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$logRoot = Join-Path $root 'logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$stdout = Join-Path $logRoot ($runId + '_stdout.log')
$stderr = Join-Path $logRoot ($runId + '_stderr.log')
$arguments = @(
    $trainer,
    '--mode', 'formal',
    '--run-id', $runId,
    '--batch-size-scenes', '36',
    '--workers', '4'
)
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$launcher = [ordered]@{
    status = 'launched'
    run_id = $runId
    process_id = $process.Id
    started_local = (Get-Date).ToString('o')
    stdout = $stdout
    stderr = $stderr
    command = ($python + ' ' + ($arguments -join ' '))
}
$launcherPath = Join-Path $logRoot 'launcher_state.json'
$launcher | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $launcherPath -Encoding utf8
Start-Sleep -Seconds 3
$process.Refresh()
if ($process.HasExited) {
    $launcher.status = 'failed_to_stay_running'
    $launcher.exit_code = $process.ExitCode
    $launcher | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $launcherPath -Encoding utf8
    throw ('R116 trainer exited during launch. Read: ' + $stderr)
}
$launcher | ConvertTo-Json -Depth 4
