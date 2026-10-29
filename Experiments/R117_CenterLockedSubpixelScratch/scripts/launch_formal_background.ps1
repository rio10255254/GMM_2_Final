$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$lock = Join-Path $root 'runs\active_run.lock'
$manifest = Join-Path $root 'data\package\manifest.json'
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if (Test-Path -LiteralPath $lock) { throw ('An R117 run is already active: ' + (Get-Content $lock -Raw)) }
if (-not (Test-Path -LiteralPath $manifest)) { throw 'The complete data package is missing.' }
$data = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($data.status -ne 'complete' -or $data.counts.train -ne 5000 -or $data.counts.validation -ne 512) { throw 'The data package is not the formal 5000/512 package.' }
$runId = 'r117_formal_scratch_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$stdout = Join-Path $logs ($runId + '_stdout.log')
$stderr = Join-Path $logs ($runId + '_stderr.log')
$arguments = @((Join-Path $root 'training\train.py'), '--mode', 'formal', '--run-id', $runId)
$process = Start-Process -FilePath python -ArgumentList $arguments -WorkingDirectory $root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
$state = [ordered]@{ status='launched'; run_id=$runId; pid=$process.Id; started_at=(Get-Date).ToString('o'); stdout=$stdout; stderr=$stderr; scratch=$true; checkpoint_loaded=$false }
$state | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs 'launcher_state.json') -Encoding UTF8
$registry = [ordered]@{ formal_run_id=$runId; pid=$process.Id; run_dir=(Join-Path (Join-Path $root 'runs') $runId); unique_formal_run=$true; status='running' }
$registry | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'runs\formal_run_registry.json') -Encoding UTF8
Write-Host ('R117 formal scratch training launched. PID ' + $process.Id) -ForegroundColor Green
Write-Host ('Run: ' + $runId)
