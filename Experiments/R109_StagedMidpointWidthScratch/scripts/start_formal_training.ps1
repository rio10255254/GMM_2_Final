param([string]$RunId = 'r109_formal_scratch_continuous_b8_20260826')
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$state=Get-Content -LiteralPath (Join-Path $root 'PREPARED_STATE.json') -Raw|ConvertFrom-Json
if(-not $state.formal_training_authorized){throw 'Formal training is not authorized by PREPARED_STATE.json'}
$lock=Join-Path $root 'runs\active_run.lock';if(Test-Path -LiteralPath $lock){throw "An R109 run is already active: $((Get-Content -LiteralPath $lock -Raw).Trim())"}
$run=Join-Path $root "runs\$RunId";if(Test-Path -LiteralPath $run){throw "Run directory already exists: $run"}
$logs=Join-Path $root 'logs';New-Item -ItemType Directory -Force -Path $logs|Out-Null;$stdout=Join-Path $logs 'formal_stdout.log';$stderr=Join-Path $logs 'formal_stderr.log';$launcher=Join-Path $logs 'launcher_state.json'
$arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root 'scripts\train.ps1'),'-RunId',$RunId,'-Epochs','48','-DetectorEpochs','6','-BatchSize','8','-Workers','4')
$process=Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
@{status='launched';run_id=$RunId;process_id=$process.Id;started_at=(Get-Date).ToString('o');stdout=$stdout;stderr=$stderr;scratch=$true;epochs=48;detector_epochs=6;batch_size=8;workers=4}|ConvertTo-Json|Set-Content -LiteralPath $launcher -Encoding utf8
Write-Host "R109 formal scratch training launched. PID=$($process.Id) Run=$RunId" -ForegroundColor Green
