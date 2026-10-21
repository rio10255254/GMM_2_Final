param(
    [ValidateSet('menu', 'help', 'show-config', 'save-config', 'first-run', 'doctor', 'build', 'infer-demo', 'infer-custom', 'train-quick', 'train-full', 'shell', 'install-system-prereqs')]
    [string]$Action = 'menu',
    [string]$InputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$LauncherPath = $MyInvocation.MyCommand.Path
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptRoot
$ConfigPath = Join-Path $ScriptRoot 'LAUNCHER_CONFIG.json'
$FormalTrainWrapperPath = Join-Path $ScriptRoot 'GeoEdge_R26_FormalTrain.ps1'
$FormalInferWrapperPath = Join-Path $ScriptRoot 'GeoEdge_R26_FormalInfer.ps1'
$Script:Cfg = $null

. $FormalTrainWrapperPath
. $FormalInferWrapperPath

function Write-Utf8BomFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $encoding = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Get-DefaultConfig {
    return [ordered]@{
        auto_detect_runtime            = $true
        image_name                     = 'geoedge-r26-handoff'
        gpu_request                    = 'all'
        inference_device               = 'cuda:0'
        training_device                = 'cuda:0'
        demo_weights                   = '../weights/r26_sm035_best_tradeoff.pth.tar'
        demo_input_dir                 = '../Demo_Input'
        demo_recon_root                = '../Reconstruct_Progress'
        train_resume_checkpoint        = '../weights/r26_sm035_best_tradeoff.pth.tar'
        train_reset_epoch              = $true
        train_reset_optimizer          = $false
        train_quick_simpletest_max_epoch = 10
    }
}

function ConvertTo-OrderedHashtable {
    param([object]$InputObject)

    $table = [ordered]@{}
    if ($null -eq $InputObject) {
        return $table
    }

    foreach ($prop in $InputObject.PSObject.Properties) {
        $table[$prop.Name] = $prop.Value
    }
    return $table
}

function Refresh-ProcessPath {
    $paths = @(
        [System.Environment]::GetEnvironmentVariable('Path', 'Machine'),
        [System.Environment]::GetEnvironmentVariable('Path', 'User')
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    $env:Path = ($paths -join ';')

    $dockerBin = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
    if ((Test-Path -LiteralPath $dockerBin) -and ($env:Path -notlike "*$dockerBin*")) {
        $env:Path = '{0};{1}' -f $env:Path, $dockerBin
    }
}

function Get-DockerCliPath {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    if ($command -and $command.Source -and (Test-Path -LiteralPath $command.Source)) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'),
        (Join-Path $env:LocalAppData 'Programs\Docker\Docker\resources\bin\docker.exe')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-DockerCliOrThrow {
    $dockerCli = Get-DockerCliPath
    if (-not $dockerCli) {
        throw 'Docker 仍不可用。請先完成 Docker Desktop 安裝。'
    }
    return $dockerCli
}

function Invoke-DockerCliProbe {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $dockerCli = Get-DockerCliPath
    if (-not $dockerCli) {
        return [pscustomobject]@{
            success   = $false
            exit_code = 127
            output    = ''
        }
    }

    try {
        $output = & $dockerCli @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    catch {
        $output = @($_.Exception.Message)
        $exitCode = if ($LASTEXITCODE) { $LASTEXITCODE } else { 1 }
    }

    return [pscustomobject]@{
        success   = ($exitCode -eq 0)
        exit_code = $exitCode
        output    = (($output | Out-String).Trim())
    }
}

function Get-DockerDesktopStatus {
    $probe = Invoke-DockerCliProbe -Arguments @('desktop', 'status')
    if (-not $probe.success) {
        return $null
    }

    foreach ($line in ($probe.output -split "`r?`n")) {
        if ($line -match '^\s*Status\s+(?<status>\S+)\s*$') {
            return $Matches.status.ToLowerInvariant()
        }
    }

    return $null
}

function Get-WslStatusInfo {
    $wslCommand = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wslCommand) {
        return [pscustomobject]@{
            installed = $false
            needs_install = $true
            output = '找不到 wsl.exe。'
        }
    }

    try {
        $output = & $wslCommand.Source --status 2>&1
        $exitCode = $LASTEXITCODE
    }
    catch {
        $output = @($_.Exception.Message)
        $exitCode = if ($LASTEXITCODE) { $LASTEXITCODE } else { 1 }
    }

    $text = ($output | Out-String).Trim()
    $normalizedText = ($text -replace "`0", '')
    $needsInstall = ($exitCode -ne 0) -and ($normalizedText -match 'wsl\.exe\s+--install')
    $needsRestart = ($exitCode -eq 0) -and ($normalizedText -match 'wsl\.exe\s+--install\s+--no-distribution')
    $virtualizationBlocked = ($normalizedText -match 'enablevirtualization') -or ($normalizedText -match 'BIOS')
    $isReady = ($exitCode -eq 0) -and (-not $needsRestart) -and (-not $virtualizationBlocked)

    return [pscustomobject]@{
        installed = $isReady
        needs_install = $needsInstall
        needs_restart = $needsRestart
        virtualization_blocked = $virtualizationBlocked
        output = $normalizedText
    }
}

function Test-IsAdministrator {
    if ($env:OS -ne 'Windows_NT') {
        return $false
    }

    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Start-ElevatedLauncherAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RequestedAction
    )

    $argList = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $LauncherPath),
        '-Action', $RequestedAction
    )

    try {
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $argList | Out-Null
    }
    catch {
        throw '無法取得系統管理員權限來安裝 WSL 2。若剛剛取消了 UAC 視窗，請重新執行 START_HERE.bat 並允許提權。'
    }
}

function Invoke-WslInstallCommand {
    if (($env:OS -eq 'Windows_NT') -and (-not (Test-IsAdministrator))) {
        throw '安裝 WSL 2 需要系統管理員權限。請重新執行 START_HERE.bat，並在跳出的 UAC 視窗中允許提權。'
    }

    $wslCommand = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if (-not $wslCommand) {
        throw '找不到 wsl.exe，無法自動安裝 WSL。'
    }

    $attempts = @(
        @('--install', '--no-distribution'),
        @('--install')
    )

    $lastText = $null
    foreach ($attemptArgs in $attempts) {
        try {
            $output = & $wslCommand.Source @attemptArgs 2>&1
            $exitCode = $LASTEXITCODE
        }
        catch {
            $output = @($_.Exception.Message)
            $exitCode = if ($LASTEXITCODE) { $LASTEXITCODE } else { 1 }
        }

        $text = ((($output | Out-String).Trim()) -replace "`0", '')
        $lastText = $text

        if ($exitCode -eq 0 -or $exitCode -eq 3010) {
            Write-Host 'WSL 安裝指令已送出。'
            Write-Host '請先重新開機，之後手動開一次 Docker Desktop 完成首次初始化，再重新雙擊 START_HERE.bat。'
            return
        }

        if ($attemptArgs.Count -gt 1) {
            continue
        }
    }

    $details = if ($lastText) { $lastText } else { '目前沒有額外的安裝輸出。' }
    throw ("WSL 自動安裝失敗。`n請改用系統管理員身分開 PowerShell，手動執行：`n  wsl --install`n`n安裝輸出：`n{0}" -f $details)
}

function Ensure-LinuxContainerPrerequisites {
    if ($env:OS -ne 'Windows_NT') {
        return
    }

    $wslInfo = Get-WslStatusInfo
    if ($wslInfo.installed) {
        return
    }

    if ($wslInfo.needs_install) {
        Write-Section '自動安裝 WSL 2'

        if (-not (Test-IsAdministrator)) {
            Write-Host '偵測到目前不是系統管理員權限，正在要求系統管理員權限安裝 WSL 2...'
            Start-ElevatedLauncherAction -RequestedAction 'install-system-prereqs'
            throw '已跳出系統管理員授權視窗以安裝 WSL 2。安裝完成並重新開機後，請再重新雙擊 START_HERE.bat。'
        }

        Invoke-WslInstallCommand
        throw 'WSL 2 安裝程序已啟動。請先重新開機，之後再重新雙擊 START_HERE.bat。'
    }

    if ($wslInfo.needs_restart -or $wslInfo.virtualization_blocked) {
        $details = if ($wslInfo.output) { $wslInfo.output } else { '目前沒有額外的 WSL 診斷輸出。' }
        throw ("WSL 2 尚未完成啟用，因此暫時無法啟動 Docker Desktop 的 Linux 容器。`n請先重新開機；若重開後仍看到相同訊息，再確認 BIOS 虛擬化與 Windows 的 Virtual Machine Platform 已啟用。`n`nWSL 檢查輸出：`n{0}" -f $details)
    }

    $details = if ($wslInfo.output) { $wslInfo.output } else { '目前沒有額外的 WSL 診斷輸出。' }
    throw ("WSL 目前不可用，因此無法啟動 Docker Desktop 的 Linux 容器。`n請先確認 WSL 2 已正確安裝並完成重開機。`n`nWSL 檢查輸出：`n{0}" -f $details)
}

function Get-HostGpuInfo {
    $gpuNames = New-Object System.Collections.Generic.List[string]
    $nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue

    if ($nvidiaSmi) {
        $lines = & $nvidiaSmi.Source --query-gpu=index,name --format=csv,noheader 2>$null
        if ($LASTEXITCODE -eq 0) {
            foreach ($line in $lines) {
                if ([string]::IsNullOrWhiteSpace($line)) {
                    continue
                }
                $parts = $line.Split(',', 2)
                if ($parts.Count -ge 2) {
                    $null = $gpuNames.Add($parts[1].Trim())
                }
                else {
                    $null = $gpuNames.Add($line.Trim())
                }
            }
        }
    }

    return [pscustomobject]@{
        nvidia_smi_found = ($null -ne $nvidiaSmi)
        gpu_count        = $gpuNames.Count
        gpu_names        = @($gpuNames.ToArray())
    }
}

function Apply-AutoRuntimeConfig {
    param($ConfigTable)

    $autoDetect = $true
    if ($ConfigTable.Contains('auto_detect_runtime')) {
        $autoDetect = [bool]$ConfigTable['auto_detect_runtime']
    }

    if (-not $autoDetect) {
        return
    }

    $gpuInfo = Get-HostGpuInfo
    if ($gpuInfo.gpu_count -gt 0) {
        $ConfigTable['gpu_request'] = 'all'
        $ConfigTable['inference_device'] = 'cuda:0'
        $ConfigTable['training_device'] = 'cuda:0'
    }
    else {
        $ConfigTable['gpu_request'] = 'disabled'
        $ConfigTable['inference_device'] = 'cpu'
        $ConfigTable['training_device'] = 'cpu'
    }
}

function Get-LauncherConfig {
    param([switch]$ApplyAutoRuntime)

    $cfg = Get-DefaultConfig
    if (Test-Path -LiteralPath $ConfigPath) {
        $loaded = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        foreach ($prop in $loaded.PSObject.Properties) {
            $cfg[$prop.Name] = $prop.Value
        }
    }

    if ($ApplyAutoRuntime) {
        Apply-AutoRuntimeConfig -ConfigTable $cfg
    }

    return [pscustomobject]$cfg
}

function Save-LauncherConfig {
    param([object]$ConfigObject)

    $configTable = ConvertTo-OrderedHashtable $ConfigObject
    $json = ([pscustomobject]$configTable) | ConvertTo-Json -Depth 6
    Write-Utf8BomFile -Path $ConfigPath -Content $json
}

function Use-DockerGpu {
    $gpuRequest = [string]$Script:Cfg.gpu_request
    if ([string]::IsNullOrWhiteSpace($gpuRequest)) {
        return $false
    }

    $normalized = $gpuRequest.Trim().ToLowerInvariant()
    return ($normalized -notin @('disabled', 'none', 'cpu', 'off'))
}

function Write-Section([string]$Text) {
    Write-Host ''
    Write-Host ('=== {0} ===' -f $Text)
}

function Write-Step([int]$Index, [int]$Total, [string]$Text) {
    Write-Host ('[{0}/{1}] {2}' -f $Index, $Total, $Text)
}

function Write-KeyValue([string]$Label, [string]$Value) {
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        Write-Host ('- {0}: {1}' -f $Label, $Value)
    }
}

function Show-ActionSummary([string]$Title, [hashtable]$Items) {
    Write-Section $Title
    foreach ($entry in $Items.GetEnumerator()) {
        $value = [string]$entry.Value
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Write-KeyValue $entry.Key $value
        }
    }
}

function Normalize-UserSuppliedPath([string]$PathText) {
    if ([string]::IsNullOrWhiteSpace($PathText)) {
        return $PathText
    }

    $normalized = $PathText.Trim()
    while ($normalized.Length -ge 2) {
        $startsDouble = $normalized.StartsWith('"')
        $endsDouble = $normalized.EndsWith('"')
        $startsSingle = $normalized.StartsWith("'")
        $endsSingle = $normalized.EndsWith("'")
        if (($startsDouble -and $endsDouble) -or ($startsSingle -and $endsSingle)) {
            $normalized = $normalized.Substring(1, $normalized.Length - 2).Trim()
            continue
        }
        break
    }

    return $normalized
}

function Get-LatestChildDirectory([string]$RootPath) {
    if ([string]::IsNullOrWhiteSpace($RootPath) -or (-not (Test-Path -LiteralPath $RootPath))) {
        return $null
    }

    return (Get-ChildItem -LiteralPath $RootPath -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
}

function Get-HostOutputDir([string]$Leaf) {
    return (Join-Path (Join-Path $PackageRoot '輸出結果') $Leaf)
}

function Test-DockerCliAvailable {
    return ($null -ne (Get-DockerCliPath))
}

function Test-DockerDaemonReady {
    $desktopStatus = Get-DockerDesktopStatus
    if ($desktopStatus -and ($desktopStatus -ne 'running')) {
        return $false
    }

    return (Invoke-DockerCliProbe -Arguments @('version', '--format', '{{.Server.Version}}')).success
}

function Get-DockerDesktopExe {
    $candidates = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path $env:LocalAppData 'Programs\Docker\Docker\Docker Desktop.exe')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

function Install-DockerDesktop {
    Write-Section '自動安裝 Docker Desktop'

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw '找不到 winget，無法自動安裝 Docker Desktop。請先手動安裝 Docker Desktop，然後重新雙擊 START_HERE.bat。'
    }

    Write-Host '未偵測到 docker，正在嘗試透過 winget 自動安裝 Docker Desktop。'
    & $winget.Source install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Desktop 自動安裝失敗。請改為手動安裝後再重試。'
    }

    Refresh-ProcessPath
}

function Start-DockerDesktop {
    $dockerCli = Get-DockerCliPath
    if ($dockerCli) {
        $startProbe = Invoke-DockerCliProbe -Arguments @('desktop', 'start', '--detach')
        if ($startProbe.success) {
            return
        }
    }

    $dockerDesktopExe = Get-DockerDesktopExe
    if ($dockerDesktopExe) {
        Start-Process -FilePath $dockerDesktopExe | Out-Null
        return
    }

    throw '找不到 Docker Desktop 主程式。請先完成 Docker Desktop 安裝。'
}

function Wait-DockerDaemonReady {
    param([int]$TimeoutSeconds = 180)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastDesktopStatus = $null
    $lastWaitLog = [datetime]::MinValue
    $lastProbe = $null
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerDaemonReady) {
            return
        }

        $desktopStatus = Get-DockerDesktopStatus
        if ($desktopStatus -and ($desktopStatus -ne $lastDesktopStatus)) {
            Write-Host ('Docker Desktop 狀態：{0}' -f $desktopStatus)
            $lastDesktopStatus = $desktopStatus
        }

        if (((Get-Date) - $lastWaitLog).TotalSeconds -ge 15) {
            if ((-not $desktopStatus) -or ($desktopStatus -eq 'running')) {
                $lastProbe = Invoke-DockerCliProbe -Arguments @('version', '--format', '{{.Server.Version}}')
            }
            Write-Host 'Docker daemon 尚未就緒，持續等待中...'
            $lastWaitLog = Get-Date
        }
        Start-Sleep -Seconds 2
    }

    $statusText = Get-DockerDesktopStatus
    if (-not $lastProbe) {
        $lastProbe = Invoke-DockerCliProbe -Arguments @('version', '--format', '{{.Server.Version}}')
    }
    $probeText = if ($lastProbe -and $lastProbe.output) { $lastProbe.output } else { '目前無額外診斷輸出。' }
    $statusLine = if ($statusText) { ('目前 Docker Desktop 狀態：{0}' -f $statusText) } else { '目前無法取得 Docker Desktop 狀態。' }
    throw ("Docker 已安裝，但 daemon 尚未就緒。{0}`n如果這是第一次安裝，請先完成 Docker Desktop 首次啟動；必要時請重新登入 Windows 或重開機後再重試。`n`n最後一次檢查輸出：`n{1}" -f $statusLine, $probeText)
}

function Ensure-DockerReady {
    Refresh-ProcessPath
    $installedJustNow = $false

    Ensure-LinuxContainerPrerequisites

    if (-not (Test-DockerCliAvailable)) {
        Install-DockerDesktop
        $installedJustNow = $true
        Refresh-ProcessPath
    }

    if (-not (Test-DockerCliAvailable)) {
        throw 'Docker 仍不可用。請先完成 Docker Desktop 安裝。'
    }

    if ($installedJustNow) {
        Write-Host 'Docker Desktop 安裝完成，正在進行首次啟動...'
        Start-DockerDesktop
        Wait-DockerDaemonReady -TimeoutSeconds 240
        return
    }

    if (-not (Test-DockerDaemonReady)) {
        Write-Host 'Docker 已安裝，但 daemon 尚未就緒，正在嘗試啟動 Docker Desktop...'
        Start-DockerDesktop
        Wait-DockerDaemonReady -TimeoutSeconds 180
    }
}

function Ensure-HostDirs {
    foreach ($path in @(
        (Get-HostOutputDir '訓練結果'),
        (Get-HostOutputDir '推論結果')
    )) {
        if (-not (Test-Path -LiteralPath $path)) {
            New-Item -ItemType Directory -Force -Path $path | Out-Null
        }
    }
}

function Test-ImageExists {
    return (Invoke-DockerCliProbe -Arguments @('image', 'inspect', [string]$Script:Cfg.image_name)).success
}

function Build-Image {
    Ensure-DockerReady
    Write-Section 'Docker Build'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '建立 / 更新 Docker 映像'
        '映像名稱' = [string]$Script:Cfg.image_name
        '訓練輸出掛載' = (Get-HostOutputDir '訓練結果')
        '推論輸出掛載' = (Get-HostOutputDir '推論結果')
    })
    $dockerCli = Get-DockerCliOrThrow
    & $dockerCli build -t $Script:Cfg.image_name $ScriptRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker 映像建立失敗。'
    }
    Write-Host ('[完成] Docker 映像已建立：{0}' -f $Script:Cfg.image_name)
}

function Ensure-Image {
    Ensure-DockerReady
    Ensure-HostDirs
    if (-not (Test-ImageExists)) {
        Write-Host ('找不到 Docker 映像 "{0}"，正在自動建立...' -f $Script:Cfg.image_name)
        Build-Image
    }
}

function Get-VolumeArg([string]$HostPath, [string]$ContainerPath) {
    return ('{0}:{1}' -f $HostPath, $ContainerPath)
}

function Invoke-DockerRun {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InnerCommand,
        [string]$ExtraHostMount,
        [string]$ExtraContainerMount
    )

    Ensure-Image

    $trainProgress = (Resolve-Path -LiteralPath (Get-HostOutputDir '訓練結果')).Path
    $reconProgress = (Resolve-Path -LiteralPath (Get-HostOutputDir '推論結果')).Path

    $dockerArgs = @(
        'run', '--rm', '-it'
    )

    if (Use-DockerGpu) {
        $dockerArgs += @('--gpus', [string]$Script:Cfg.gpu_request)
    }

    $dockerArgs += @(
        '-v', (Get-VolumeArg $trainProgress '/app/Traing_Progress'),
        '-v', (Get-VolumeArg $reconProgress '/app/Reconstruct_Progress')
    )

    if ($ExtraHostMount) {
        $resolvedExtra = (Resolve-Path -LiteralPath $ExtraHostMount).Path
        $dockerArgs += @('-v', (Get-VolumeArg $resolvedExtra $ExtraContainerMount))
    }

    $dockerArgs += @(
        '-w', '/app/Model',
        [string]$Script:Cfg.image_name,
        'bash', '-lc', $InnerCommand
    )

    $dockerCli = Get-DockerCliOrThrow
    & $dockerCli @dockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker 容器執行失敗。'
    }
}

function Open-ContainerShell {
    Ensure-Image

    $trainProgress = (Resolve-Path -LiteralPath (Get-HostOutputDir '訓練結果')).Path
    $reconProgress = (Resolve-Path -LiteralPath (Get-HostOutputDir '推論結果')).Path

    $dockerArgs = @(
        'run', '--rm', '-it'
    )

    if (Use-DockerGpu) {
        $dockerArgs += @('--gpus', [string]$Script:Cfg.gpu_request)
    }

    $dockerArgs += @(
        '-v', (Get-VolumeArg $trainProgress '/app/Traing_Progress'),
        '-v', (Get-VolumeArg $reconProgress '/app/Reconstruct_Progress'),
        '-w', '/app/Model',
        [string]$Script:Cfg.image_name,
        'bash'
    )

    $dockerCli = Get-DockerCliOrThrow
    & $dockerCli @dockerArgs
    if ($LASTEXITCODE -ne 0) {
        throw '開啟容器 shell 失敗。'
    }
}

function Start-DemoInference {
    $reconRoot = Get-HostOutputDir '推論結果'
    $beforeDir = Get-LatestChildDirectory -RootPath $reconRoot

    Write-Section '示範影像推論'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '封包內示範影像（demo / smoke）'
        '輸入資料夾' = [string]$Script:Cfg.demo_input_dir
        '權重' = (Resolve-FormalInferPath (Get-FormalR26InferRecipe).deploy_checkpoint_relative)
        '裝置' = [string]$Script:Cfg.inference_device
        '結果根目錄' = $reconRoot
    })
    Show-FormalR26InferSummary -InputDir ([string]$Script:Cfg.demo_input_dir) -ReconRoot ([string]$Script:Cfg.demo_recon_root) -Device ([string]$Script:Cfg.inference_device)
    $cmd = Get-FormalR26InferDockerCommand -InputDir ([string]$Script:Cfg.demo_input_dir) -ReconRoot ([string]$Script:Cfg.demo_recon_root) -Device ([string]$Script:Cfg.inference_device)
    Write-Step 1 3 '確認 Docker 環境與映像'
    Write-Step 2 3 '啟動推論'
    Write-Host '底下若持續出現 [n/N] Processing ...，表示推論仍在進行中。'
    Invoke-DockerRun -InnerCommand $cmd
    Write-Step 3 3 '整理結果位置'
    $afterDir = Get-LatestChildDirectory -RootPath $reconRoot
    if ($afterDir -and (($null -eq $beforeDir) -or ($afterDir.FullName -ne $beforeDir.FullName) -or ($afterDir.LastWriteTime -gt $beforeDir.LastWriteTime))) {
        Write-Host ('[完成] 示範推論已結束。結果資料夾：{0}' -f $afterDir.FullName)
    }
    else {
        Write-Host ('[完成] 示範推論已結束。請查看：{0}' -f $reconRoot)
    }
}

function Start-CustomInference {
    param([string]$HostInputDir)

    if (-not $HostInputDir) {
        $HostInputDir = Read-Host '請輸入主機端要推論的資料夾路徑或單一影像檔路徑'
    }
    $HostInputDir = Normalize-UserSuppliedPath $HostInputDir
    if (-not $HostInputDir) {
        throw '未提供輸入資料夾。'
    }
    if (-not (Test-Path -LiteralPath $HostInputDir)) {
        throw ('找不到輸入資料夾：{0}' -f $HostInputDir)
    }

    $resolvedInputPath = (Resolve-Path -LiteralPath $HostInputDir).Path
    $inputItem = Get-Item -LiteralPath $resolvedInputPath
    $inputDirToUse = $resolvedInputPath
    $tempInputDir = $null
    $reconRoot = Get-HostOutputDir '推論結果'
    $beforeDir = Get-LatestChildDirectory -RootPath $reconRoot

    Write-Section '自訂資料推論'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '外部資料驗證'
        '輸入' = $(if ($inputItem.PSIsContainer) { '資料夾: ' + $resolvedInputPath } else { '單一影像: ' + $resolvedInputPath })
        '權重' = (Resolve-FormalInferPath (Get-FormalR26InferRecipe).deploy_checkpoint_relative)
        '裝置' = [string]$Script:Cfg.inference_device
        '結果根目錄' = $reconRoot
    })

    if (-not $inputItem.PSIsContainer) {
        $tempInputDir = Join-Path $env:TEMP ('geoedge_single_input_' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force -Path $tempInputDir | Out-Null
        Copy-Item -LiteralPath $resolvedInputPath -Destination (Join-Path $tempInputDir $inputItem.Name) -Force
        $inputDirToUse = $tempInputDir
        Write-Host ('偵測到單一影像檔，將只對此檔案做推論：{0}' -f $resolvedInputPath)
    }

    Show-FormalR26InferSummary -InputDir '/external_input' -ReconRoot ([string]$Script:Cfg.demo_recon_root) -Device ([string]$Script:Cfg.inference_device)
    $cmd = Get-FormalR26InferDockerCommand -InputDir '/external_input' -ReconRoot ([string]$Script:Cfg.demo_recon_root) -Device ([string]$Script:Cfg.inference_device)

    try {
        Write-Step 1 3 '確認 Docker 環境與映像'
        Write-Step 2 3 '啟動推論'
        Write-Host '底下若持續出現 [n/N] Processing ...，表示推論仍在進行中。'
        Invoke-DockerRun -InnerCommand $cmd -ExtraHostMount $inputDirToUse -ExtraContainerMount '/external_input:ro'
        Write-Step 3 3 '整理結果位置'
        $afterDir = Get-LatestChildDirectory -RootPath $reconRoot
        if ($afterDir -and (($null -eq $beforeDir) -or ($afterDir.FullName -ne $beforeDir.FullName) -or ($afterDir.LastWriteTime -gt $beforeDir.LastWriteTime))) {
            Write-Host ('[完成] 外部資料推論已結束。結果資料夾：{0}' -f $afterDir.FullName)
        }
        else {
            Write-Host ('[完成] 外部資料推論已結束。請查看：{0}' -f $reconRoot)
        }
    }
    finally {
        if ($tempInputDir) {
            Remove-Item -LiteralPath $tempInputDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-TrainFlags {
    param([bool]$Quick)

    $flags = @()
    if ($Script:Cfg.train_resume_checkpoint) {
        $flags += ('--resume-checkpoint {0}' -f $Script:Cfg.train_resume_checkpoint)
    }
    if ([bool]$Script:Cfg.train_reset_epoch) {
        $flags += '--reset-epoch'
    }
    if ([bool]$Script:Cfg.train_reset_optimizer) {
        $flags += '--reset-optimizer'
    }
    if ($Script:Cfg.training_device) {
        $flags += ('--device {0}' -f $Script:Cfg.training_device)
    }
    if ($Quick -and $Script:Cfg.train_quick_simpletest_max_epoch) {
        $flags += ('--simpletest-max-epoch {0}' -f $Script:Cfg.train_quick_simpletest_max_epoch)
    }
    return ($flags -join ' ')
}

function Start-QuickTrain {
    $progressRoot = Join-Path (Get-HostOutputDir '訓練結果') '_smoketest'
    $beforeDir = Get-LatestChildDirectory -RootPath $progressRoot

    Write-Section '快速訓練測試'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '快速 smoke test（不是正式長訓結果）'
        '起始 checkpoint' = [string]$Script:Cfg.train_resume_checkpoint
        '最大 epoch' = [string]$Script:Cfg.train_quick_simpletest_max_epoch
        '裝置' = [string]$Script:Cfg.training_device
        '結果根目錄' = $progressRoot
    })
    $cmd = @(
        'python GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py',
        (Get-TrainFlags -Quick $true),
        '--progress-root /app/Traing_Progress/_smoketest'
    ) -join ' '
    Write-Step 1 3 '確認 Docker 環境與映像'
    Write-Step 2 3 '啟動訓練'
    Write-Host '底下若持續出現 Starting Epoch / [RUN] / [SUMMARY] 訊息，表示訓練仍在進行中。'
    Invoke-DockerRun -InnerCommand $cmd
    Write-Step 3 3 '整理結果位置'
    $afterDir = Get-LatestChildDirectory -RootPath $progressRoot
    if ($afterDir -and (($null -eq $beforeDir) -or ($afterDir.FullName -ne $beforeDir.FullName) -or ($afterDir.LastWriteTime -gt $beforeDir.LastWriteTime))) {
        Write-Host ('[完成] 快速訓練已結束。結果資料夾：{0}' -f $afterDir.FullName)
    }
    else {
        Write-Host ('[完成] 快速訓練已結束。請查看：{0}' -f $progressRoot)
    }
}

function Start-FullTrain {
    $progressRoot = Get-HostOutputDir '訓練結果'
    $beforeDir = Get-LatestChildDirectory -RootPath $progressRoot

    Write-Section '正式 R26 重現訓練'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '正式 R26 歷史重現訓練'
        'seed checkpoint' = (Resolve-FormalR26Path (Get-FormalR26Recipe).seed_checkpoint_relative)
        '裝置' = [string]$Script:Cfg.training_device
        '結果根目錄' = $progressRoot
    })
    Show-FormalR26RecipeSummary -ProgressRoot $progressRoot -Device ([string]$Script:Cfg.training_device)
    $cmd = Get-FormalR26TrainDockerCommand -Device ([string]$Script:Cfg.training_device)
    Write-Step 1 3 '確認 Docker 環境與映像'
    Write-Step 2 3 '啟動訓練'
    Write-Host '底下若持續出現 Starting Epoch / [RUN] / [SUMMARY] 訊息，表示訓練仍在進行中。'
    Invoke-DockerRun -InnerCommand $cmd
    Write-Step 3 3 '整理結果位置'
    $afterDir = Get-LatestChildDirectory -RootPath $progressRoot
    if ($afterDir -and (($null -eq $beforeDir) -or ($afterDir.FullName -ne $beforeDir.FullName) -or ($afterDir.LastWriteTime -gt $beforeDir.LastWriteTime))) {
        Write-Host ('[完成] 完整訓練已結束。結果資料夾：{0}' -f $afterDir.FullName)
    }
    else {
        Write-Host ('[完成] 完整訓練已結束。請查看：{0}' -f $progressRoot)
    }
}

function Test-ContainerCuda {
    if (-not (Use-DockerGpu)) {
        return [pscustomobject]@{
            skipped = $true
            success = $true
            output  = '目前未啟用 GPU，已略過容器 CUDA 驗證。'
        }
    }

    Ensure-Image

    $innerCommand = @'
python - <<'PY'
import torch
print('cuda_available=' + str(torch.cuda.is_available()))
print('device_count=' + str(torch.cuda.device_count()))
PY
'@

    $dockerArgs = @('run', '--rm', '--gpus', [string]$Script:Cfg.gpu_request, '-w', '/app/Model', [string]$Script:Cfg.image_name, 'bash', '-lc', $innerCommand)
    $dockerCli = Get-DockerCliOrThrow
    $output = & $dockerCli @dockerArgs 2>&1
    $text = ($output | Out-String).Trim()

    return [pscustomobject]@{
        skipped = $false
        success = (($LASTEXITCODE -eq 0) -and ($text -match 'cuda_available=True') -and ($text -match 'device_count=\d+'))
        output  = $text
    }
}

function Invoke-FirstRun {
    Write-Section '第一次啟動自動初始化'

    Write-Step 1 4 '確認輸出資料夾'
    Ensure-HostDirs
    $Script:Cfg = Get-LauncherConfig -ApplyAutoRuntime

    Write-Step 2 4 '偵測主機 GPU / 裝置策略'
    $gpuInfo = Get-HostGpuInfo
    if ($gpuInfo.gpu_count -gt 0) {
        Write-Host ('已偵測到 {0} 張 NVIDIA GPU：{1}' -f $gpuInfo.gpu_count, ($gpuInfo.gpu_names -join ' | '))
    }
    else {
        Write-Host '未偵測到可用的 NVIDIA GPU / nvidia-smi。已自動把 launcher 預設裝置切到 CPU。'
        Write-Host '如果之後補裝 NVIDIA 驅動或換到有 GPU 的機器，再執行一次 START_HERE.bat 即可自動切回 CUDA。'
    }

    Write-Step 3 4 '確認 Docker / WSL 與映像'
    Ensure-DockerReady
    Ensure-Image

    if (Use-DockerGpu) {
        Write-Host '正在驗證容器內 CUDA 是否可用...'
        $gpuTest = Test-ContainerCuda
        if (-not $gpuTest.success) {
            throw ("已偵測到主機端 NVIDIA GPU，但容器目前無法使用 CUDA。`n請先確認：`n1. Windows 上的 NVIDIA 驅動已正確安裝且 `nvidia-smi` 可用`n2. Docker Desktop 已完成啟動`n3. 必要時先重開機再重試`n`n容器檢查輸出：`n{0}" -f $gpuTest.output)
        }
        Write-Host '容器內 CUDA 驗證通過。'
    }

    Write-Step 4 4 '儲存初始化設定'
    Save-LauncherConfig -ConfigObject $Script:Cfg
    Show-ActionSummary '初始化摘要' ([ordered]@{
        '路線' = 'Docker / WSL'
        '映像名稱' = [string]$Script:Cfg.image_name
        '推論裝置' = [string]$Script:Cfg.inference_device
        '訓練裝置' = [string]$Script:Cfg.training_device
        '推論輸出根目錄' = (Get-HostOutputDir '推論結果')
        '訓練輸出根目錄' = (Get-HostOutputDir '訓練結果')
    })
    Write-Host '初始化完成，啟動器設定已自動寫入 LAUNCHER_CONFIG.json。'
}

function Show-Help {
    Write-Host 'GeoEdge_R26_Handoff Docker/WSL 進階啟動器'
    Write-Host '這是 Docker / WSL 進階入口；一般使用者請先用 START_HERE.bat，只有明確要固定走容器路線時才用 START_HERE_DOCKER.bat。'
    Write-Host '支援邊界：以 Windows + PowerShell + Docker Desktop(Linux containers) + WSL 2 為主要目標，不保證在 macOS / 原生 Linux / 受限企業環境下一鍵成功。'
    Write-Host '可用動作：'
    Write-Host '  menu          開啟互動式選單'
    Write-Host '  first-run     第一次啟動自動初始化（建議）'
    Write-Host '  doctor        顯示目前環境檢查結果'
    Write-Host '  build         建立 Docker 映像'
    Write-Host '  infer-demo    使用正式 r26_sm035 權重做示範影像推論'
    Write-Host '  infer-custom  使用正式 r26_sm035 權重做外部資料推論'
    Write-Host '  train-quick   執行 smoke 訓練測試（輸出到 _smoketest）'
    Write-Host '  train-full    執行正式 R26 歷史重現訓練'
    Write-Host '  shell         開啟容器內互動 shell'
    Write-Host '  show-config   顯示目前自動合併後的啟動器設定'
    Write-Host '  save-config   將目前自動合併後的設定寫回 LAUNCHER_CONFIG.json'
}

function Show-Config {
    $Script:Cfg | ConvertTo-Json -Depth 6
}

function Save-CurrentConfig {
    Save-LauncherConfig -ConfigObject $Script:Cfg
    Write-Host '已將目前設定寫回 LAUNCHER_CONFIG.json。'
}

function Show-Doctor {
    $gpuInfo = Get-HostGpuInfo
    $desktopStatus = Get-DockerDesktopStatus
    $wslInfo = Get-WslStatusInfo
    Write-Section '環境檢查'
    Write-Host ('docker CLI：{0}' -f ($(if (Test-DockerCliAvailable) { '可用' } else { '找不到' })))
    Write-Host ('docker daemon：{0}' -f ($(if (Test-DockerDaemonReady) { '已就緒' } else { '未就緒' })))
    Write-Host ('Docker Desktop 狀態：{0}' -f ($(if ($desktopStatus) { $desktopStatus } else { '未知' })))
    Write-Host ('WSL：{0}' -f ($(if ($wslInfo.installed) { '可用' } elseif ($wslInfo.needs_install) { '未安裝' } elseif ($wslInfo.needs_restart) { '待重開機' } elseif ($wslInfo.virtualization_blocked) { '虛擬化未完成' } else { '不可用' })))
    Write-Host ('nvidia-smi：{0}' -f ($(if ($gpuInfo.nvidia_smi_found) { '可用' } else { '找不到' })))
    Write-Host ('偵測到 GPU 張數：{0}' -f $gpuInfo.gpu_count)
    if ($gpuInfo.gpu_count -gt 0) {
        Write-Host ('GPU 名稱：{0}' -f ($gpuInfo.gpu_names -join ' | '))
    }
    Write-Host ('目前 gpu_request：{0}' -f $Script:Cfg.gpu_request)
    Write-Host ('目前 inference_device：{0}' -f $Script:Cfg.inference_device)
    Write-Host ('目前 training_device：{0}' -f $Script:Cfg.training_device)
    Write-Host ('主機訓練輸出根目錄：{0}' -f (Get-HostOutputDir '訓練結果'))
    Write-Host ('主機推論輸出根目錄：{0}' -f (Get-HostOutputDir '推論結果'))
    Write-Host ('Docker 映像是否存在：{0}' -f ($(if ((Test-DockerCliAvailable) -and (Test-DockerDaemonReady) -and (Test-ImageExists)) { '是' } else { '否' })))
    $formal = Get-FormalR26PresetStatus
    Write-Host ('formal winner：{0}' -f $formal.winner_name)
    Write-Host ('formal seed：{0}' -f $formal.seed)
    Write-Host ('formal deterministic：{0}' -f $formal.deterministic)
    Write-Host ('formal deploy checkpoint：{0}' -f ($(if ($formal.deploy_checkpoint_exists) { '存在' } else { '缺少' })))
    Write-Host ('formal seed checkpoint：{0}' -f ($(if ($formal.seed_checkpoint_exists) { '存在' } else { '缺少' })))
    Write-Host ('formal PSF：{0}' -f ($(if ($formal.formal_psf_exists) { '存在' } else { '缺少' })))
}

function Show-Menu {
    while ($true) {
        Write-Section 'GeoEdge 啟動選單'
        Write-Host ('封包根目錄：{0}' -f $ScriptRoot)
        Write-Host ('GPU 指派設定：{0}' -f $Script:Cfg.gpu_request)
        Write-Host ('推論裝置：{0}' -f $Script:Cfg.inference_device)
        Write-Host ('訓練裝置：{0}' -f $Script:Cfg.training_device)
        Write-Host ('推論結果：{0}' -f (Get-HostOutputDir '推論結果'))
        Write-Host ('訓練結果：{0}' -f (Get-HostOutputDir '訓練結果'))
        Write-Host ''
        Write-Host '1. 執行第一次啟動自動初始化'
        Write-Host '2. 建立 Docker 映像'
        Write-Host '3. 使用封包內示範影像做推論（demo / smoke）'
        Write-Host '4. 使用你自己的資料夾或單張影像做推論（外部驗證）'
        Write-Host '5. 執行快速訓練測試（smoke，輸出到 _smoketest）'
        Write-Host '6. 執行正式 R26 歷史重現訓練'
        Write-Host '7. 開啟容器互動 shell'
        Write-Host '8. 顯示環境檢查結果'
        Write-Host '9. 顯示目前啟動器設定'
        Write-Host '0. 離開'
        $choice = Read-Host '請選擇'

        switch ($choice) {
            '1' {
                Invoke-FirstRun
                $Script:Cfg = Get-LauncherConfig -ApplyAutoRuntime
            }
            '2' { Build-Image }
            '3' { Start-DemoInference }
            '4' { Start-CustomInference }
            '5' { Start-QuickTrain }
            '6' { Start-FullTrain }
            '7' { Open-ContainerShell }
            '8' { Show-Doctor }
            '9' { Show-Config }
            '0' { return }
            default { Write-Host ('未知選項：{0}' -f $choice) }
        }
    }
}

Refresh-ProcessPath
$Script:Cfg = Get-LauncherConfig -ApplyAutoRuntime

try {
    switch ($Action) {
        'menu' { Show-Menu }
        'help' { Show-Help }
        'show-config' { Show-Config }
        'save-config' { Save-CurrentConfig }
        'first-run' { Invoke-FirstRun }
        'install-system-prereqs' { Invoke-WslInstallCommand }
        'doctor' { Show-Doctor }
        'build' { Build-Image }
        'infer-demo' { Start-DemoInference }
        'infer-custom' { Start-CustomInference -HostInputDir $InputDir }
        'train-quick' { Start-QuickTrain }
        'train-full' { Start-FullTrain }
        'shell' { Open-ContainerShell }
    }
}
catch {
    Write-Host ''
    Write-Host ('[錯誤] {0}' -f $_.Exception.Message)
    exit 1
}

