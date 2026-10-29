param([int]$RefreshSeconds = 10)
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ErrorActionPreference = 'SilentlyContinue'
$ExperimentRoot = Split-Path -Parent $PSScriptRoot
$RunRoot = Join-Path $ExperimentRoot 'runs\formal_8192'
$MarkerPath = Join-Path $ExperimentRoot 'runs\launcher_logs\active_formal_run.json'
$StdoutPath = Join-Path $ExperimentRoot 'runs\launcher_logs\formal_stdout.log'
$StderrPath = Join-Path $ExperimentRoot 'runs\launcher_logs\formal_stderr.log'

function Read-JsonSafe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    for ($Attempt = 0; $Attempt -lt 3; $Attempt++) {
        try { return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json }
        catch { Start-Sleep -Milliseconds 100 }
    }
    return $null
}

while ($true) {
    $Now = Get-Date
    $Marker = Read-JsonSafe $MarkerPath
    $Latest = Read-JsonSafe (Join-Path $RunRoot 'latest.json')
    $Status = Read-JsonSafe (Join-Path $RunRoot 'status.json')
    $DevInitial = Read-JsonSafe (Join-Path $RunRoot 'dev_initial.json')
    $UpdatePath = Join-Path $RunRoot 'updates.jsonl'
    $Rows = @()
    if (Test-Path -LiteralPath $UpdatePath) {
        $Rows = @(Get-Content -LiteralPath $UpdatePath -Tail 8 | ForEach-Object { $_ | ConvertFrom-Json })
    }
    $Last = if ($Rows.Count) { $Rows[-1] } else { $null }
    $PidValue = if ($Marker) { [int]$Marker.process_id } else { 0 }
    $Process = if ($PidValue) { Get-Process -Id $PidValue } else { $null }
    $Alive = $null -ne $Process
    $Step = if ($Last) { [int]$Last.step } elseif ($Status) { [int]$Status.step } else { 0 }
    $Total = 8192
    $Percent = 100.0 * $Step / $Total
    $ElapsedSeconds = if ($Marker) { ($Now.ToUniversalTime() - [datetime]$Marker.started_utc).TotalSeconds } else { 0 }
    $Rate = if ($Step -gt 0 -and $ElapsedSeconds -gt 0) { $Step / $ElapsedSeconds } else { 0 }
    $RemainingSeconds = if ($Rate -gt 0) { ($Total - $Step) / $Rate } else { 0 }
    $Eta = if ($RemainingSeconds -gt 0) { $Now.AddSeconds($RemainingSeconds) } else { $null }
    $CheckpointHashOk = $false
    if ($Latest -and (Test-Path -LiteralPath ([System.IO.Path]::Combine($ProjectRoot, $Latest.path)))) {
        $CheckpointHash = (Get-FileHash -LiteralPath $Latest.path -Algorithm SHA256).Hash.ToLower()
        $CheckpointHashOk = $CheckpointHash -eq $Latest.sha256
    }
    $DriveInfo = Get-PSDrive D,H | Select-Object Name,@{N='FreeGiB';E={[math]::Round($_.Free/1GB,2)}}
    $LatestDev = Get-ChildItem -LiteralPath $RunRoot -Filter 'dev_*.json' | Where-Object Name -ne 'dev_initial.json' | Sort-Object Name | Select-Object -Last 1
    $LatestDevValue = if ($LatestDev) { Read-JsonSafe $LatestDev.FullName } else { $null }

    Clear-Host
    Write-Host 'R148v2 正式訓練前景監控' -ForegroundColor Cyan
    Write-Host ('更新時間：{0:yyyy-MM-dd HH:mm:ss}   每 {1} 秒刷新' -f $Now,$RefreshSeconds)
    Write-Host ('實驗位置：{0}' -f $ExperimentRoot)
    Write-Host ('程序：PID {0}   存活={1}   標記={2}' -f $PidValue,$Alive,$Marker.status) -ForegroundColor $(if($Alive){'Green'}else{'Red'})
    Write-Host ('進度：{0} / {1}  ({2:N2}%)   Epoch {3} / 15' -f $Step,$Total,$Percent,([math]::Floor([math]::Max(0,$Step-1)/512))) -ForegroundColor Yellow
    if ($Rate -gt 0) {
        Write-Host ('平均速度：{0:N3} update/s   已耗時 {1:hh\:mm\:ss}   預估完成 {2:yyyy-MM-dd HH:mm:ss}' -f $Rate,[timespan]::FromSeconds($ElapsedSeconds),$Eta)
    }
    if ($Last) {
        Write-Host ''
        Write-Host '最新一次訓練數值' -ForegroundColor Cyan
        Write-Host ('Loss={0:N6}  Image={1:N6}  Gradient={2:N6}  Pair={3:N6}  Boundary={4:N6}  Observation={5:N6}' -f $Last.loss,$Last.image,$Last.gradient,$Last.pair_output,$Last.boundary,$Last.observation)
        Write-Host ('Category={0}  Parent={1}  LR={2:E3}  Eta=[{3}]' -f $Last.category,$Last.parent_id,$Last.learning_rate,(($Last.eta | ForEach-Object { '{0:N5}' -f $_ }) -join ', '))
    }
    Write-Host ''
    Write-Host '開發資料與保存點' -ForegroundColor Cyan
    Write-Host ('訓練前完整開發誤差：{0}' -f $(if($DevInitial){'{0:N6}' -f $DevInitial.mean_loss}else{'尚未產生'}))
    Write-Host ('最新階段開發誤差：{0}' -f $(if($LatestDevValue){('{0} = {1:N6}' -f $LatestDev.Name,$LatestDevValue.mean_loss)}else{'尚未到第512次'}))
    Write-Host ('最新保存點：step {0}   SHA-256核對={1}' -f $(if($Latest){$Latest.step}else{0}),$CheckpointHashOk)
    Write-Host ''
    Write-Host '最近八筆更新' -ForegroundColor Cyan
    foreach ($Row in $Rows) {
        Write-Host ('{0,5}  loss={1,9:N5}  img={2,8:N4}  grad={3,8:N4}  pair={4,7:N4}  boundary={5,7:N4}  {6}' -f $Row.step,$Row.loss,$Row.image,$Row.gradient,$Row.pair_output,$Row.boundary,$Row.category)
    }
    Write-Host ''
    Write-Host '儲存空間' -ForegroundColor Cyan
    $DriveInfo | Format-Table -AutoSize | Out-String | Write-Host
    $StderrBytes = if (Test-Path -LiteralPath $StderrPath) { (Get-Item -LiteralPath $StderrPath).Length } else { 0 }
    Write-Host ('錯誤輸出大小：{0} bytes' -f $StderrBytes) -ForegroundColor $(if($StderrBytes -eq 0){'Green'}else{'Red'})
    if ($StderrBytes -gt 0) { Get-Content -LiteralPath $StderrPath -Tail 8 | Write-Host -ForegroundColor Red }
    Write-Host ''
    Write-Host '按 Ctrl+C 只會關閉這個監控畫面，不會停止背景訓練。' -ForegroundColor DarkGray
    Start-Sleep -Seconds $RefreshSeconds
}
