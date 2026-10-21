$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Python = 'C:\Users\Rio\anaconda3\python.exe'
$LogDir = Join-Path $Root 'runs\launcher_logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Stdout = Join-Path $LogDir ("formal_" + $Stamp + ".stdout.log")
$Stderr = Join-Path $LogDir ("formal_" + $Stamp + ".stderr.log")
$Arguments = @('-u', (Join-Path $PSScriptRoot 'launch_r88.py'), '--run-kind', 'formal', '--device', 'cuda:0', '--num-workers', '4')
$Process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $Root -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -WindowStyle Hidden -PassThru
$Record = [ordered]@{ process_id = $Process.Id; started_at = (Get-Date).ToString('o'); stdout = $Stdout; stderr = $Stderr }
$Record | ConvertTo-Json | Set-Content -Path (Join-Path $LogDir 'formal_launcher_process.json') -Encoding UTF8
$Record | ConvertTo-Json
