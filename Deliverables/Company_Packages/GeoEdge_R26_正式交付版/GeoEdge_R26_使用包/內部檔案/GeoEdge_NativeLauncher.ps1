param(
    [ValidateSet('menu', 'help', 'show-config', 'save-config', 'first-run', 'doctor', 'infer-demo', 'infer-custom', 'train-full')]
    [string]$Action = 'menu',
    [string]$InputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptRoot
$ConfigPath = Join-Path $ScriptRoot 'NATIVE_LAUNCHER_CONFIG.json'
$RequirementsPath = Join-Path $ScriptRoot 'requirements.txt'
$FormalTrainWrapperPath = Join-Path $ScriptRoot 'GeoEdge_R26_FormalTrain.ps1'
$FormalInferWrapperPath = Join-Path $ScriptRoot 'GeoEdge_R26_FormalInfer.ps1'
$PortableRuntimeRoot = Join-Path $ScriptRoot 'portable_runtime'
$PortableRuntimeArchive = Join-Path $ScriptRoot 'portable_runtime_bundle.zip'
$PortableRuntimeStatePath = Join-Path $PortableRuntimeRoot '.geoedge_portable_runtime.json'
$Script:Cfg = $null
$Script:LastRuntimeInfo = $null

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
        auto_detect_runtime             = $true
        python_strategy                 = 'auto'
        python_command                  = 'python'
        venv_dir                        = '.venv'
        inference_device                = 'cuda:0'
        training_device                 = 'cuda:0'
        demo_weights                    = 'weights\r26_sm035_best_tradeoff.pth.tar'
        demo_input_dir                  = 'Demo_Input'
        demo_recon_root                 = '..\輸出結果\推論結果'
        train_progress_root             = '..\輸出結果\訓練結果'
        train_resume_checkpoint         = 'weights\r26_sm035_best_tradeoff.pth.tar'
        train_reset_epoch               = $true
        train_reset_optimizer           = $false
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

function Get-LauncherConfig {
    $cfg = Get-DefaultConfig
    if (Test-Path -LiteralPath $ConfigPath) {
        $loaded = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
        foreach ($prop in $loaded.PSObject.Properties) {
            $cfg[$prop.Name] = $prop.Value
        }
    }

    $legacyReconRoots = @('Reconstruct_Progress', 'Analyses\Reconstruct_Progress')
    if ($legacyReconRoots -contains [string]$cfg['demo_recon_root']) {
        $cfg['demo_recon_root'] = '..\輸出結果\推論結果'
    }

    $legacyTrainRoots = @('', 'Traing_Progress', '.\Traing_Progress')
    if ($legacyTrainRoots -contains [string]$cfg['train_progress_root']) {
        $cfg['train_progress_root'] = '..\輸出結果\訓練結果'
    }

    $strategy = ([string]$cfg['python_strategy']).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($strategy)) {
        $cfg['python_strategy'] = 'auto'
    }

    return [pscustomobject]$cfg
}

function Save-LauncherConfig {
    param([object]$ConfigObject)

    $configTable = ConvertTo-OrderedHashtable $ConfigObject
    $json = ([pscustomobject]$configTable) | ConvertTo-Json -Depth 6
    Write-Utf8BomFile -Path $ConfigPath -Content $json
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

function Resolve-ConfiguredPath([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }
    if ([System.IO.Path]::IsPathRooted($Text)) {
        return $Text
    }
    return (Join-Path $ScriptRoot $Text)
}

function Ensure-HostDirs {
    $paths = @(
        (Resolve-ConfiguredPath ([string]$Script:Cfg.train_progress_root))
        (Resolve-ConfiguredPath ([string]$Script:Cfg.demo_recon_root))
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique

    foreach ($path in $paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            New-Item -ItemType Directory -Force -Path $path | Out-Null
        }
    }
}

function Add-UniqueString {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    $normalized = $Value.Trim()
    foreach ($item in $List) {
        if ($item.Equals($normalized, [System.StringComparison]::OrdinalIgnoreCase)) {
            return
        }
    }
    $null = $List.Add($normalized)
}

function Get-CommandSourcePaths([string]$Name) {
    $results = New-Object System.Collections.Generic.List[string]

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        Add-UniqueString -List $results -Value $cmd.Source
    }

    $cmdExe = Join-Path $env:SystemRoot 'System32\cmd.exe'
    if (Test-Path -LiteralPath $cmdExe) {
        try {
            $whereOutput = & $cmdExe /d /c "where $Name 2>nul"
            if ($LASTEXITCODE -eq 0) {
                foreach ($line in $whereOutput) {
                    Add-UniqueString -List $results -Value $line
                }
            }
        }
        catch {
        }
    }

    return @($results.ToArray())
}

function Get-PyLauncherInstalledPythonPaths {
    $results = New-Object System.Collections.Generic.List[string]
    $pyCandidates = New-Object System.Collections.Generic.List[string]
    foreach ($pyPath in (Get-CommandSourcePaths -Name 'py')) {
        Add-UniqueString -List $pyCandidates -Value $pyPath
    }
    $windowsPy = Join-Path $env:SystemRoot 'py.exe'
    if (Test-Path -LiteralPath $windowsPy) {
        Add-UniqueString -List $pyCandidates -Value $windowsPy
    }
    foreach ($pyPath in $pyCandidates) {
        try {
            $output = & $pyPath -0p 2>$null
            if ($LASTEXITCODE -ne 0) {
                continue
            }
            foreach ($line in $output) {
                if ($line -match '([A-Za-z]:\\.*?python(?:w)?\.exe)') {
                    Add-UniqueString -List $results -Value $Matches[1]
                }
            }
        }
        catch {
        }
    }
    return @($results.ToArray())
}

function Get-CommonPythonInstallPaths {
    $results = New-Object System.Collections.Generic.List[string]
    $roots = @(
        (Join-Path $env:LocalAppData 'Programs\Python'),
        $env:ProgramFiles,
        (Join-Path $env:ProgramFiles 'Python'),
        'C:\'
    )

    foreach ($root in $roots) {
        if ([string]::IsNullOrWhiteSpace($root) -or (-not (Test-Path -LiteralPath $root))) {
            continue
        }

        foreach ($dir in (Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue)) {
            if ($dir.Name -notlike 'Python*') {
                continue
            }
            $pythonExe = Join-Path $dir.FullName 'python.exe'
            if (Test-Path -LiteralPath $pythonExe) {
                Add-UniqueString -List $results -Value $pythonExe
            }
        }
    }

    return @($results.ToArray())
}

function Get-NvidiaSmiPath {
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($path in (Get-CommandSourcePaths -Name 'nvidia-smi')) {
        Add-UniqueString -List $candidates -Value $path
    }

    $commonPaths = @(
        (Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe'),
        (Join-Path $env:SystemRoot 'System32\nvidia-smi.exe')
    )
    foreach ($path in $commonPaths) {
        if (Test-Path -LiteralPath $path) {
            Add-UniqueString -List $candidates -Value $path
        }
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-HostGpuInfo {
    $gpuNames = New-Object System.Collections.Generic.List[string]
    $nvidiaSmi = Get-NvidiaSmiPath
    $cudaVersion = $null

    if ($nvidiaSmi) {
        $summary = & $nvidiaSmi 2>$null
        if ($LASTEXITCODE -eq 0) {
            $summaryText = ($summary | Out-String)
            if ($summaryText -match 'CUDA Version:\s*([0-9]+\.[0-9]+)') {
                $cudaVersion = $Matches[1]
            }
        }

        $lines = & $nvidiaSmi --query-gpu=index,name --format=csv,noheader 2>$null
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
        nvidia_smi_path  = $nvidiaSmi
        cuda_version     = $cudaVersion
        gpu_count        = $gpuNames.Count
        gpu_names        = @($gpuNames.ToArray())
    }
}

function New-PythonRuntime {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [string[]]$PrefixArgs = @(),
        [string]$Label = 'python'
    )

    return [pscustomobject]@{
        executable = $Executable
        prefix_args = @($PrefixArgs)
        label = $Label
    }
}

function Test-PythonExecutableUsable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [string[]]$PrefixArgs = @()
    )

    try {
        & $Executable @($PrefixArgs + @('--version')) *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Get-PythonRuntimeKey {
    param([object]$Runtime)

    return ('{0}|{1}' -f ([string]$Runtime.executable).ToLowerInvariant(), (($Runtime.prefix_args -join ' ').ToLowerInvariant()))
}

function Test-PortableRuntimeAvailable {
    return ((Test-Path -LiteralPath (Join-Path $PortableRuntimeRoot 'python.exe')) -or (Test-Path -LiteralPath $PortableRuntimeArchive))
}

function Ensure-PortableRuntime {
    if (-not (Test-Path -LiteralPath (Join-Path $PortableRuntimeRoot 'python.exe'))) {
        if (-not (Test-Path -LiteralPath $PortableRuntimeArchive)) {
            return $null
        }

        Write-Section '展開獨立 GPU runtime'
        Expand-Archive -LiteralPath $PortableRuntimeArchive -DestinationPath $PortableRuntimeRoot -Force
    }

    if (-not (Test-Path -LiteralPath (Join-Path $PortableRuntimeRoot 'python.exe'))) {
        throw ('獨立 GPU runtime 展開後仍找不到 python.exe：{0}' -f $PortableRuntimeRoot)
    }

    $currentRoot = (Resolve-Path -LiteralPath $PortableRuntimeRoot).Path
    $needsUnpack = $true
    if (Test-Path -LiteralPath $PortableRuntimeStatePath) {
        try {
            $state = Get-Content -LiteralPath $PortableRuntimeStatePath -Raw | ConvertFrom-Json
            if ($state.portable_root -eq $currentRoot) {
                $needsUnpack = $false
            }
        }
        catch {
            $needsUnpack = $true
        }
    }

    if ($needsUnpack) {
        $unpackExe = Join-Path $PortableRuntimeRoot 'Scripts\conda-unpack.exe'
        if (Test-Path -LiteralPath $unpackExe) {
            Write-Host '正在修正獨立 GPU runtime 的實際路徑...'
            Push-Location $PortableRuntimeRoot
            try {
                & $unpackExe | Out-Host
                if ($LASTEXITCODE -ne 0) {
                    throw 'conda-unpack 執行失敗。'
                }
            }
            finally {
                Pop-Location
            }
        }

        $stateJson = (@{
            portable_root = $currentRoot
            fixed_at = (Get-Date).ToString('o')
        } | ConvertTo-Json -Depth 4)
        Write-Utf8BomFile -Path $PortableRuntimeStatePath -Content $stateJson
    }

    return (New-PythonRuntime -Executable (Join-Path $PortableRuntimeRoot 'python.exe') -Label 'portable-runtime')
}

function Get-BasePythonRuntimeCandidates {
    $candidates = New-Object System.Collections.Generic.List[object]
    $discoveredPaths = New-Object System.Collections.Generic.List[string]

    $configured = [string]$Script:Cfg.python_command
    if (-not [string]::IsNullOrWhiteSpace($configured)) {
        if ([System.IO.Path]::IsPathRooted($configured) -and (Test-Path -LiteralPath $configured)) {
            $null = $candidates.Add((New-PythonRuntime -Executable $configured -Label 'configured'))
        }
        else {
            $cmd = Get-Command $configured -ErrorAction SilentlyContinue
            if ($cmd -and $cmd.Source) {
                $null = $candidates.Add((New-PythonRuntime -Executable $cmd.Source -Label ('configured:{0}' -f $configured)))
            }
        }
    }

    foreach ($path in (Get-CommandSourcePaths -Name 'python')) {
        Add-UniqueString -List $discoveredPaths -Value $path
    }
    foreach ($path in (Get-PyLauncherInstalledPythonPaths)) {
        Add-UniqueString -List $discoveredPaths -Value $path
    }
    foreach ($path in (Get-CommonPythonInstallPaths)) {
        Add-UniqueString -List $discoveredPaths -Value $path
    }

    foreach ($path in $discoveredPaths) {
        $null = $candidates.Add((New-PythonRuntime -Executable $path -Label 'python'))
    }

    foreach ($pyPath in (Get-CommandSourcePaths -Name 'py')) {
        $null = $candidates.Add((New-PythonRuntime -Executable $pyPath -PrefixArgs @('-3') -Label 'py -3'))
    }

    $valid = New-Object System.Collections.Generic.List[object]
    $seen = @{}
    foreach ($candidate in $candidates) {
        $key = Get-PythonRuntimeKey -Runtime $candidate
        if ($seen.ContainsKey($key)) {
            continue
        }

        if (Test-PythonExecutableUsable -Executable $candidate.executable -PrefixArgs $candidate.prefix_args) {
            $seen[$key] = $true
            $null = $valid.Add($candidate)
        }
    }

    if ($valid.Count -gt 0) {
        return @($valid.ToArray())
    }

    throw '找不到可用的 Python。請先安裝 Python 3，或在 NATIVE_LAUNCHER_CONFIG.json 指定 python_command。'
}

function Get-BasePythonRuntime {
    return (Get-BasePythonRuntimeCandidates | Select-Object -First 1)
}

function Get-VenvPythonRuntime {
    $venvRoot = Resolve-ConfiguredPath ([string]$Script:Cfg.venv_dir)
    $venvPython = Join-Path $venvRoot 'Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        if (Test-PythonExecutableUsable -Executable $venvPython) {
            return (New-PythonRuntime -Executable $venvPython -Label 'venv')
        }
    }
    return $null
}

function Invoke-PythonRuntimeCapture {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Runtime,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    try {
        $output = & $Runtime.executable @($Runtime.prefix_args + $Arguments) 2>&1
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

function Invoke-PythonRuntimePassthrough {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Runtime,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Runtime.executable @($Runtime.prefix_args + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw ('Python 指令執行失敗：{0}' -f (($Arguments -join ' ')))
    }
}

function Invoke-PythonRuntimeTempScriptCapture {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Runtime,
        [Parameter(Mandatory = $true)]
        [string]$Code
    )

    $tempPath = Join-Path $env:TEMP ('geoedge_native_' + [guid]::NewGuid().ToString('N') + '.py')
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tempPath, $Code, $encoding)
    try {
        return (Invoke-PythonRuntimeCapture -Runtime $Runtime -Arguments @($tempPath))
    }
    finally {
        Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
    }
}

function Test-RequirementsSatisfied {
    param([object]$Runtime)

    $code = @'
import importlib.util as u

mods = ["torch", "torchvision", "torchmetrics", "cv2", "scipy", "matplotlib", "tqdm", "numpy", "h5py"]
missing = [m for m in mods if u.find_spec(m) is None]
if missing:
    print("MISSING=" + ",".join(missing))
    raise SystemExit(1)
print("REQUIREMENTS_OK")
'@

    $probe = Invoke-PythonRuntimeTempScriptCapture -Runtime $Runtime -Code $code
    return [pscustomobject]@{
        success = $probe.success
        output = $probe.output
    }
}

function Ensure-RuntimeRequirements {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Runtime,
        [bool]$AllowInstall = $false
    )

    $req = Test-RequirementsSatisfied -Runtime $Runtime
    if ($req.success) {
        if ($AllowInstall -and ($Runtime.label -eq 'venv')) {
            $gpuInfo = Get-HostGpuInfo
            if ($gpuInfo.gpu_count -gt 0) {
                $torchInfo = Get-TorchRuntimeInfo -Runtime $Runtime
                if (-not ($torchInfo.success -and $torchInfo.cuda_available -and ($torchInfo.device_count -gt 0))) {
                    Install-Requirements -Runtime $Runtime
                    return (Test-RequirementsSatisfied -Runtime $Runtime)
                }
            }
        }
        return $req
    }

    if ($AllowInstall -and ($Runtime.label -eq 'venv')) {
        Install-Requirements -Runtime $Runtime
        return (Test-RequirementsSatisfied -Runtime $Runtime)
    }

    return $req
}

function Get-MissingRequirementsFromOutput {
    param([string]$OutputText)

    if ([string]::IsNullOrWhiteSpace($OutputText)) {
        return @()
    }

    if ($OutputText -match 'MISSING=([A-Za-z0-9_,\.-]+)') {
        return @($Matches[1].Split(',') | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }

    return @()
}

function Ensure-Venv {
    param([object]$BaseRuntime)

    $venvRoot = Resolve-ConfiguredPath ([string]$Script:Cfg.venv_dir)
    $existing = Get-VenvPythonRuntime
    if ($existing) {
        return $existing
    }

    if (Test-Path -LiteralPath $venvRoot) {
        Write-Host '發現不可用的 .venv，將刪除後重建。'
        Remove-Item -LiteralPath $venvRoot -Recurse -Force
    }

    Write-Section '建立 Python venv'
    Invoke-PythonRuntimePassthrough -Runtime $BaseRuntime -Arguments @('-m', 'venv', $venvRoot) | Out-Host

    $created = Get-VenvPythonRuntime
    if (-not $created) {
        throw ('venv 建立後仍找不到 python.exe：{0}' -f $venvRoot)
    }
    return $created
}

function Get-PyTorchGpuInstallPlan {
    param([object]$GpuInfo)

    if (($null -eq $GpuInfo) -or ($GpuInfo.gpu_count -le 0)) {
        return $null
    }

    $cudaVersionText = [string]$GpuInfo.cuda_version
    if ([string]::IsNullOrWhiteSpace($cudaVersionText)) {
        return $null
    }

    try {
        $cudaVersion = [version]$cudaVersionText
    }
    catch {
        return $null
    }

    if ($cudaVersion -ge [version]'12.8') {
        return [pscustomobject]@{
            label = 'CUDA 12.8'
            index_url = 'https://download.pytorch.org/whl/cu128'
        }
    }

    if ($cudaVersion -ge [version]'12.6') {
        return [pscustomobject]@{
            label = 'CUDA 12.6'
            index_url = 'https://download.pytorch.org/whl/cu126'
        }
    }

    if ($cudaVersion -ge [version]'11.8') {
        return [pscustomobject]@{
            label = 'CUDA 11.8'
            index_url = 'https://download.pytorch.org/whl/cu118'
        }
    }

    return $null
}

function Install-Requirements {
    param([object]$Runtime)

    Write-Section '安裝 Python 套件'
    Invoke-PythonRuntimePassthrough -Runtime $Runtime -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip') | Out-Host
    $gpuInfo = Get-HostGpuInfo
    $torchPlan = Get-PyTorchGpuInstallPlan -GpuInfo $gpuInfo
    if ($torchPlan) {
        Write-Host ('[GPU] 使用官方 PyTorch {0} wheel index 安裝 GPU 版 torch / torchvision。' -f $torchPlan.label)
        Invoke-PythonRuntimePassthrough -Runtime $Runtime -Arguments @(
            '-m', 'pip', 'install',
            '--upgrade',
            '--force-reinstall',
            '--no-cache-dir',
            '--index-url', $torchPlan.index_url,
            'torch',
            'torchvision'
        ) | Out-Host
    }
    Invoke-PythonRuntimePassthrough -Runtime $Runtime -Arguments @('-m', 'pip', 'install', '-r', $RequirementsPath) | Out-Host
}

function Resolve-ActivePythonRuntime {
    param([bool]$ProvisionIfNeeded = $false)

    $strategy = ([string]$Script:Cfg.python_strategy).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($strategy)) {
        $strategy = 'auto'
    }

    $baseCandidates = @()
    $base = $null
    $baseError = $null
    try {
        $baseCandidates = @(Get-BasePythonRuntimeCandidates)
        $base = $baseCandidates | Select-Object -First 1
    }
    catch {
        $baseError = $_.Exception.Message
    }

    if ($strategy -eq 'system') {
        if (-not $base) {
            throw $baseError
        }
        $req = Ensure-RuntimeRequirements -Runtime $base -AllowInstall $false
        if (-not $req.success) {
            throw ("目前設定為 system Python，但缺少需求套件。`n檢查輸出：`n{0}`n`n建議先補齊需求套件，或改為 auto 讓 launcher 自動挑選。" -f $req.output)
        }
        return $base
    }

    if ($strategy -eq 'portable') {
        $portable = Ensure-PortableRuntime
        if (-not $portable) {
            throw '目前設定為 portable，但主包內找不到獨立 GPU runtime。'
        }
        $req = Ensure-RuntimeRequirements -Runtime $portable -AllowInstall $false
        if (-not $req.success) {
            throw ("獨立 GPU runtime 需求套件尚未就緒。`n檢查輸出：`n{0}" -f $req.output)
        }
        return $portable
    }

    if ($strategy -eq 'venv') {
        $venv = Get-VenvPythonRuntime
        if ((-not $venv) -and $ProvisionIfNeeded) {
            if (-not $base) {
                throw ('找不到可用的 base Python 來建立 venv。{0}' -f $baseError)
            }
            $venv = Ensure-Venv -BaseRuntime $base
        }
        if (-not $venv) {
            throw '目前設定為 venv，但尚未建立 .venv。請先執行 first-run。'
        }
        $req = Ensure-RuntimeRequirements -Runtime $venv -AllowInstall $ProvisionIfNeeded
        if (-not $req.success) {
            throw ("venv 需求套件尚未就緒。`n檢查輸出：`n{0}" -f $req.output)
        }
        return $venv
    }

    $readyEntries = New-Object System.Collections.Generic.List[object]
    $hostEntries = New-Object System.Collections.Generic.List[object]
    $hostIssues = New-Object System.Collections.Generic.List[string]

    foreach ($candidate in $baseCandidates) {
        $req = Ensure-RuntimeRequirements -Runtime $candidate -AllowInstall $false
        if (-not $req.success) {
            $missing = @(Get-MissingRequirementsFromOutput -OutputText $req.output)
            if ($missing.Count -gt 0) {
                $null = $hostIssues.Add(('system Python `{0}` 缺少套件：{1}' -f $candidate.executable, ($missing -join ', ')))
            }
            else {
                $null = $hostIssues.Add(('system Python `{0}` 套件檢查失敗：{1}' -f $candidate.executable, $req.output))
            }
            continue
        }

        $torchInfo = Get-TorchRuntimeInfo -Runtime $candidate
        $entry = [pscustomobject]@{
            runtime = $candidate
            requirements = $req
            torch_info = $torchInfo
            priority = 0
        }
        $null = $readyEntries.Add($entry)
        $null = $hostEntries.Add($entry)
    }

    $gpuInfo = Get-HostGpuInfo
    $hostCudaReady = @($hostEntries | Where-Object {
        $_.torch_info.success -and $_.torch_info.cuda_available -and ($_.torch_info.device_count -gt 0)
    })

    $venv = Get-VenvPythonRuntime
    $shouldProvisionVenv = $false
    if ((-not $venv) -and $ProvisionIfNeeded -and $base) {
        if ($hostEntries.Count -eq 0) {
            $shouldProvisionVenv = $true
        }
        elseif (($gpuInfo.gpu_count -gt 0) -and ($hostCudaReady.Count -eq 0)) {
            $shouldProvisionVenv = $true
        }
    }
    if ($shouldProvisionVenv) {
        $venv = Ensure-Venv -BaseRuntime $base
    }
    if ($venv) {
        $venvReq = Ensure-RuntimeRequirements -Runtime $venv -AllowInstall $ProvisionIfNeeded
        if ($venvReq.success) {
            $venvTorch = Get-TorchRuntimeInfo -Runtime $venv
            $entry = [pscustomobject]@{
                runtime = $venv
                requirements = $venvReq
                torch_info = $venvTorch
                priority = 1
            }
            $null = $readyEntries.Add($entry)
            $null = $hostEntries.Add($entry)
        }
        else {
            $missing = @(Get-MissingRequirementsFromOutput -OutputText $venvReq.output)
            if ($missing.Count -gt 0) {
                $null = $hostIssues.Add(('venv `{0}` 缺少套件：{1}' -f $venv.executable, ($missing -join ', ')))
            }
            else {
                $null = $hostIssues.Add(('venv `{0}` 套件檢查失敗：{1}' -f $venv.executable, $venvReq.output))
            }
        }
    }

    $portableEntry = $null
    $portableIssue = $null
    if (Test-PortableRuntimeAvailable) {
        $portable = Ensure-PortableRuntime
        if ($portable) {
            $portableReq = Ensure-RuntimeRequirements -Runtime $portable -AllowInstall $false
            if ($portableReq.success) {
                $portableTorch = Get-TorchRuntimeInfo -Runtime $portable
                $portableEntry = [pscustomobject]@{
                    runtime = $portable
                    requirements = $portableReq
                    torch_info = $portableTorch
                    priority = 2
                }
                $null = $readyEntries.Add($portableEntry)
            }
            else {
                $missing = @(Get-MissingRequirementsFromOutput -OutputText $portableReq.output)
                if ($missing.Count -gt 0) {
                    $portableIssue = ('獨立 GPU 補丁缺少套件：{0}' -f ($missing -join ', '))
                }
                else {
                    $portableIssue = ('獨立 GPU 補丁套件檢查失敗：{0}' -f $portableReq.output)
                }
            }
        }
    }

    if ($readyEntries.Count -eq 0) {
        if (-not $base) {
            throw ('找不到可用的 Python runtime。{0}' -f $baseError)
        }
        $baseReq = Ensure-RuntimeRequirements -Runtime $base -AllowInstall $false
        if ($venv) {
            $venvReq = Ensure-RuntimeRequirements -Runtime $venv -AllowInstall $false
            if (-not $venvReq.success) {
                throw ("找不到需求套件已就緒的 Python runtime。`n`nsystem Python 檢查輸出：`n{0}`n`nvenv 檢查輸出：`n{1}" -f $baseReq.output, $venvReq.output)
            }
        }
        throw ("system Python 缺少需求套件，且目前沒有可用的 venv。`n檢查輸出：`n{0}" -f $baseReq.output)
    }

    if ($gpuInfo.gpu_count -gt 0) {
        $hostCudaReady = @($hostEntries | Where-Object {
            $_.torch_info.success -and $_.torch_info.cuda_available -and ($_.torch_info.device_count -gt 0)
        } | Sort-Object priority)
        if ($hostCudaReady.Count -gt 0) {
            return $hostCudaReady[0].runtime
        }

        Write-Host '[GPU] 已偵測到 NVIDIA GPU，但本機 Python 環境目前無法直接使用 CUDA。'
        foreach ($issue in $hostIssues) {
            Write-Host ('[GPU] {0}' -f $issue)
        }
        Write-Host '[GPU] 建議先補齊本機 GPU/CUDA Python 環境；若仍無法使用，再改用獨立 GPU 補丁。'

        if ($portableEntry) {
            if ($portableEntry.torch_info.success -and $portableEntry.torch_info.cuda_available -and ($portableEntry.torch_info.device_count -gt 0)) {
                Write-Host '[GPU] 目前改以獨立 GPU 補丁作為最後備援。'
                return $portableEntry.runtime
            }
            Write-Host '[GPU] 獨立 GPU 補丁已存在，但 CUDA 仍不可用，先改用 CPU。'
        }
        elseif (-not [string]::IsNullOrWhiteSpace($portableIssue)) {
            Write-Host ('[GPU] {0}' -f $portableIssue)
            Write-Host '[GPU] 請先修復獨立 GPU 補丁，再重試。'
        }
        else {
            Write-Host '[GPU] 尚未安裝獨立 GPU 補丁。需要時可用離線方式安裝。'
        }

        if ($hostEntries.Count -gt 0) {
            return (($hostEntries | Sort-Object priority | Select-Object -First 1).runtime)
        }
    }

    if ($hostEntries.Count -gt 0) {
        return (($hostEntries | Sort-Object priority | Select-Object -First 1).runtime)
    }

    if ($portableEntry) {
        return $portableEntry.runtime
    }

    throw '找不到可用的 Python runtime。'
}

function Get-TorchRuntimeInfo {
    param([object]$Runtime)

    $code = @'
import torch

print("cuda_available=" + str(torch.cuda.is_available()))
print("device_count=" + str(torch.cuda.device_count()))
'@
    $probe = Invoke-PythonRuntimeTempScriptCapture -Runtime $Runtime -Code $code
    $cudaAvailable = $false
    $deviceCount = 0
    if ($probe.output -match 'cuda_available=True') {
        $cudaAvailable = $true
    }
    if ($probe.output -match 'device_count=(\d+)') {
        $deviceCount = [int]$Matches[1]
    }
    return [pscustomobject]@{
        success = $probe.success
        cuda_available = $cudaAvailable
        device_count = $deviceCount
        output = $probe.output
    }
}

function Apply-AutoRuntimeConfig {
    param(
        $ConfigTable,
        [object]$Runtime,
        [object]$TorchInfo
    )

    $autoDetect = $true
    if ($ConfigTable.Contains('auto_detect_runtime')) {
        $autoDetect = [bool]$ConfigTable['auto_detect_runtime']
    }
    if (-not $autoDetect) {
        return
    }

    if ($null -eq $TorchInfo) {
        $TorchInfo = Get-TorchRuntimeInfo -Runtime $Runtime
    }
    if ($TorchInfo.success -and $TorchInfo.cuda_available -and ($TorchInfo.device_count -gt 0)) {
        $ConfigTable['inference_device'] = 'cuda:0'
        $ConfigTable['training_device'] = 'cuda:0'
    }
    else {
        $ConfigTable['inference_device'] = 'cpu'
        $ConfigTable['training_device'] = 'cpu'
    }
}

function Ensure-NativeReady {
    Ensure-HostDirs
    $runtime = Resolve-ActivePythonRuntime -ProvisionIfNeeded $true
    $torchInfo = Get-TorchRuntimeInfo -Runtime $runtime
    $configTable = ConvertTo-OrderedHashtable $Script:Cfg
    Apply-AutoRuntimeConfig -ConfigTable $configTable -Runtime $runtime -TorchInfo $torchInfo
    $Script:Cfg = [pscustomobject]$configTable
    $Script:LastRuntimeInfo = [pscustomobject]@{
        runtime = $runtime
        torch_info = $torchInfo
    }
    return $runtime
}

function Show-SelectedRuntime([object]$Runtime) {
    $torchInfo = $null
    if ($Script:LastRuntimeInfo -and $Script:LastRuntimeInfo.runtime -and ((Get-PythonRuntimeKey -Runtime $Script:LastRuntimeInfo.runtime) -eq (Get-PythonRuntimeKey -Runtime $Runtime))) {
        $torchInfo = $Script:LastRuntimeInfo.torch_info
    }
    if ($null -eq $torchInfo) {
        $torchInfo = Get-TorchRuntimeInfo -Runtime $Runtime
    }

    Write-KeyValue 'Python runtime' ('{0} ({1})' -f $Runtime.executable, $Runtime.label)
    if ($torchInfo.success) {
        if ($torchInfo.cuda_available -and ($torchInfo.device_count -gt 0)) {
            Write-KeyValue 'Runtime CUDA' ('可用，device_count={0}' -f $torchInfo.device_count)
        }
        else {
            Write-KeyValue 'Runtime CUDA' '不可用，已改用 CPU'
        }
    }
}

function Invoke-FirstRun {
    Write-Section 'Native 第一次啟動自動初始化'

    Write-Step 1 4 '確認輸出資料夾'
    Ensure-HostDirs

    Write-Step 2 4 '檢查 Python runtime 與需求套件'
    $runtime = Ensure-NativeReady

    Write-Step 3 4 '偵測 GPU / CUDA 狀態'
    $gpuInfo = Get-HostGpuInfo
    $torchInfo = Get-TorchRuntimeInfo -Runtime $runtime

    if ($gpuInfo.gpu_count -gt 0) {
        Write-Host ('主機端已偵測到 {0} 張 NVIDIA GPU：{1}' -f $gpuInfo.gpu_count, ($gpuInfo.gpu_names -join ' | '))
        if ($gpuInfo.cuda_version) {
            Write-Host ('主機端 nvidia-smi CUDA 版本：{0}' -f $gpuInfo.cuda_version)
        }
    }
    else {
        Write-Host '主機端未偵測到 NVIDIA GPU / nvidia-smi。'
    }

    if ($torchInfo.cuda_available) {
        Write-Host ('Python runtime CUDA 可用，device_count={0}' -f $torchInfo.device_count)
    }
    else {
        Write-Host 'Python runtime CUDA 不可用，launcher 已自動切到 CPU。'
    }

    Write-Step 4 4 '儲存初始化設定'
    Save-LauncherConfig -ConfigObject $Script:Cfg
    $routeLabel = switch ($runtime.label) {
        'portable-runtime' { '獨立 GPU runtime' }
        'venv' { '主包本地 .venv' }
        default { '本機 Windows Python' }
    }
    Show-ActionSummary '初始化摘要' ([ordered]@{
        '路線' = $routeLabel
        'Python' = ('{0} ({1})' -f $runtime.executable, $runtime.label)
        '推論裝置' = [string]$Script:Cfg.inference_device
        '訓練裝置' = [string]$Script:Cfg.training_device
        '推論輸出根目錄' = (Resolve-ConfiguredPath ([string]$Script:Cfg.demo_recon_root))
        '訓練輸出根目錄' = (Resolve-ConfiguredPath ([string]$Script:Cfg.train_progress_root))
    })
    Write-Host '初始化完成。現在可直接執行示範推論、外部資料推論或訓練。'
}

function Show-Help {
    Write-Host 'GeoEdge_R26_Handoff Native 啟動器'
    Write-Host '這條路線會先嘗試直接使用本機 Python / GPU；只有 host 缺件時才建立或使用封包內 .venv。仍不足時，最後才退到獨立 GPU 補丁或 Docker/WSL。'
    Write-Host '可用動作：'
    Write-Host '  menu          開啟互動式選單'
    Write-Host '  first-run     檢查 / 準備本機 Python runtime（建議）'
    Write-Host '  doctor        顯示目前 native 環境檢查結果'
    Write-Host '  infer-demo    使用封包內示範影像做推論'
    Write-Host '  infer-custom  指定主機資料夾做推論'
    Write-Host '  train-full    執行基於歷史 R26 baseline 的完整重新訓練'
    Write-Host '  show-config   顯示目前 native launcher 設定'
    Write-Host '  save-config   將目前設定寫回 NATIVE_LAUNCHER_CONFIG.json'
}

function Show-Config {
    $Script:Cfg | ConvertTo-Json -Depth 6
}

function Save-CurrentConfig {
    Save-LauncherConfig -ConfigObject $Script:Cfg
    Write-Host '已將目前設定寫回 NATIVE_LAUNCHER_CONFIG.json。'
}

function Show-Doctor {
    Write-Section 'Native 環境檢查'

    $baseRuntime = $null
    try {
        $baseRuntime = Get-BasePythonRuntime
    }
    catch {
        Write-Host ('base python：不可用 ({0})' -f $_.Exception.Message)
    }

    $venvRuntime = Get-VenvPythonRuntime
    Write-Host ('python_strategy：{0}' -f $Script:Cfg.python_strategy)
    Write-Host ('venv 是否存在：{0}' -f ($(if ($venvRuntime) { '是' } else { '否' })))

    if ($baseRuntime) {
        Write-Host ('base python：{0} ({1})' -f $baseRuntime.executable, $baseRuntime.label)
        $baseReq = Test-RequirementsSatisfied -Runtime $baseRuntime
        Write-Host ('base python requirements：{0}' -f ($(if ($baseReq.success) { 'OK' } else { '缺少套件' })))
    }

    $portableRuntime = $null
    if (Test-PortableRuntimeAvailable) {
        try {
            $portableRuntime = Ensure-PortableRuntime
            Write-Host ('獨立 GPU runtime：{0}' -f $portableRuntime.executable)
            $portableReq = Test-RequirementsSatisfied -Runtime $portableRuntime
            Write-Host ('獨立 GPU runtime requirements：{0}' -f ($(if ($portableReq.success) { 'OK' } else { '缺少套件' })))
        }
        catch {
            Write-Host ('獨立 GPU runtime：不可用 ({0})' -f $_.Exception.Message)
        }
    }

    if ($venvRuntime) {
        Write-Host ('venv python：{0}' -f $venvRuntime.executable)
        $venvReq = Test-RequirementsSatisfied -Runtime $venvRuntime
        Write-Host ('venv requirements：{0}' -f ($(if ($venvReq.success) { 'OK' } else { '缺少套件' })))
    }

    $runtime = $null
    try {
        $runtime = Resolve-ActivePythonRuntime -ProvisionIfNeeded $false
        Write-Host ('目前可用 runtime：{0} ({1})' -f $runtime.executable, $runtime.label)
        $torchInfo = Get-TorchRuntimeInfo -Runtime $runtime
        Write-Host ('torch cuda：{0}' -f ($(if ($torchInfo.cuda_available) { '可用' } else { '不可用' })))
        Write-Host ('torch device_count：{0}' -f $torchInfo.device_count)
    }
    catch {
        Write-Host ('目前可用 runtime：不可用 ({0})' -f $_.Exception.Message)
    }

    $gpuInfo = Get-HostGpuInfo
    Write-Host ('nvidia-smi：{0}' -f ($(if ($gpuInfo.nvidia_smi_found) { '可用' } else { '找不到' })))
    Write-Host ('偵測到 GPU 張數：{0}' -f $gpuInfo.gpu_count)
    if ($gpuInfo.gpu_count -gt 0) {
        Write-Host ('GPU 名稱：{0}' -f ($gpuInfo.gpu_names -join ' | '))
        if ($gpuInfo.cuda_version) {
            Write-Host ('主機端 CUDA 版本：{0}' -f $gpuInfo.cuda_version)
        }
    }
    Write-Host ('目前 inference_device：{0}' -f $Script:Cfg.inference_device)
    Write-Host ('目前 training_device：{0}' -f $Script:Cfg.training_device)
    Write-Host ('推論輸出根目錄：{0}' -f (Resolve-ConfiguredPath ([string]$Script:Cfg.demo_recon_root)))
    Write-Host ('訓練輸出根目錄：{0}' -f (Resolve-ConfiguredPath ([string]$Script:Cfg.train_progress_root)))
    $formal = Get-FormalR26PresetStatus
    Write-Host ('formal winner：{0}' -f $formal.winner_name)
    Write-Host ('formal seed：{0}' -f $formal.seed)
    Write-Host ('formal deterministic：{0}' -f $formal.deterministic)
    Write-Host ('formal deploy checkpoint：{0}' -f ($(if ($formal.deploy_checkpoint_exists) { '存在' } else { '缺少' })))
    Write-Host ('formal seed checkpoint：{0}' -f ($(if ($formal.seed_checkpoint_exists) { '存在' } else { '缺少' })))
    Write-Host ('formal PSF：{0}' -f ($(if ($formal.formal_psf_exists) { '存在' } else { '缺少' })))
}

function Start-DemoInference {
    $inputDir = Resolve-ConfiguredPath ([string]$Script:Cfg.demo_input_dir)
    $reconRoot = Resolve-ConfiguredPath ([string]$Script:Cfg.demo_recon_root)
    $beforeDir = Get-LatestChildDirectory -RootPath $reconRoot

    Write-Section 'Native 示範影像推論'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '封包內示範影像（demo / smoke）'
        '輸入資料夾' = $inputDir
        '權重' = (Resolve-FormalInferPath (Get-FormalR26InferRecipe).deploy_checkpoint_relative)
        '裝置' = [string]$Script:Cfg.inference_device
        '結果根目錄' = $reconRoot
    })
    Write-Step 1 3 '準備執行環境'
    $runtime = Ensure-NativeReady
    Show-SelectedRuntime -Runtime $runtime
    Write-KeyValue '實際推論裝置' ([string]$Script:Cfg.inference_device)
    Show-FormalR26InferSummary -InputDir $inputDir -ReconRoot $reconRoot -Device ([string]$Script:Cfg.inference_device)
    Write-Step 2 3 '啟動推論'
    Write-Host '底下若持續出現 [n/N] Processing ...，表示推論仍在進行中。'
    Invoke-PythonRuntimePassthrough -Runtime $runtime -Arguments (Get-FormalR26InferNativeArgs -InputDir $inputDir -ReconRoot $reconRoot -Device ([string]$Script:Cfg.inference_device))
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

    $reconRoot = Resolve-ConfiguredPath ([string]$Script:Cfg.demo_recon_root)
    $resolvedInputPath = (Resolve-Path -LiteralPath $HostInputDir).Path
    $inputItem = Get-Item -LiteralPath $resolvedInputPath
    $inputDirToUse = $resolvedInputPath
    $tempInputDir = $null
    $beforeDir = Get-LatestChildDirectory -RootPath $reconRoot

    Write-Section 'Native 自訂資料推論'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '外部資料驗證'
        '輸入' = $(if ($inputItem.PSIsContainer) { '資料夾: ' + $resolvedInputPath } else { '單一影像: ' + $resolvedInputPath })
        '權重' = (Resolve-FormalInferPath (Get-FormalR26InferRecipe).deploy_checkpoint_relative)
        '裝置' = [string]$Script:Cfg.inference_device
        '結果根目錄' = $reconRoot
    })
    Write-Step 1 3 '準備執行環境'
    $runtime = Ensure-NativeReady
    Show-SelectedRuntime -Runtime $runtime
    Write-KeyValue '實際推論裝置' ([string]$Script:Cfg.inference_device)

    try {
        if (-not $inputItem.PSIsContainer) {
            $tempInputDir = Join-Path $env:TEMP ('geoedge_single_input_' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Force -Path $tempInputDir | Out-Null
            Copy-Item -LiteralPath $resolvedInputPath -Destination (Join-Path $tempInputDir $inputItem.Name) -Force
            $inputDirToUse = $tempInputDir
            Write-Host ('偵測到單一影像檔，將只對此檔案做推論：{0}' -f $resolvedInputPath)
        }

        Write-Step 2 3 '啟動推論'
        Write-Host '底下若持續出現 [n/N] Processing ...，表示推論仍在進行中。'
        Show-FormalR26InferSummary -InputDir $inputDirToUse -ReconRoot $reconRoot -Device ([string]$Script:Cfg.inference_device)
        Invoke-PythonRuntimePassthrough -Runtime $runtime -Arguments (Get-FormalR26InferNativeArgs -InputDir $inputDirToUse -ReconRoot $reconRoot -Device ([string]$Script:Cfg.inference_device))

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

function Start-FullTrain {
    $progressRoot = Resolve-ConfiguredPath ([string]$Script:Cfg.train_progress_root)
    $beforeDir = Get-LatestChildDirectory -RootPath $progressRoot

    Write-Section 'Native R26 完整重新訓練'
    Show-ActionSummary '本次執行' ([ordered]@{
        '模式' = '基於歷史 R26 baseline 的完整重新訓練'
        'seed checkpoint' = (Resolve-FormalR26Path (Get-FormalR26Recipe).seed_checkpoint_relative)
        '裝置' = [string]$Script:Cfg.training_device
        '結果根目錄' = $progressRoot
    })
    Write-Step 1 3 '準備執行環境'
    $runtime = Ensure-NativeReady
    Show-SelectedRuntime -Runtime $runtime
    Write-KeyValue '實際訓練裝置' ([string]$Script:Cfg.training_device)
    Show-FormalR26RecipeSummary -ProgressRoot $progressRoot -Device ([string]$Script:Cfg.training_device)
    Write-Step 2 3 '啟動訓練'
    Write-Host '底下若持續出現 Starting Epoch / [RUN] / [SUMMARY] 訊息，表示訓練仍在進行中。'
    Invoke-PythonRuntimePassthrough -Runtime $runtime -Arguments (Get-FormalR26TrainNativeArgs -ProgressRoot $progressRoot -Device ([string]$Script:Cfg.training_device))
    Write-Step 3 3 '整理結果位置'
    $afterDir = Get-LatestChildDirectory -RootPath $progressRoot
    if ($afterDir -and (($null -eq $beforeDir) -or ($afterDir.FullName -ne $beforeDir.FullName) -or ($afterDir.LastWriteTime -gt $beforeDir.LastWriteTime))) {
        Write-Host ('[完成] 完整訓練已結束。結果資料夾：{0}' -f $afterDir.FullName)
    }
    else {
        Write-Host ('[完成] 完整訓練已結束。請查看：{0}' -f $progressRoot)
    }
}

function Show-Menu {
    while ($true) {
        Write-Section 'GeoEdge Native 啟動選單'
        Write-Host ('封包根目錄：{0}' -f $ScriptRoot)
        Write-Host ('python_strategy：{0}' -f $Script:Cfg.python_strategy)
        Write-Host ('推論裝置：{0}' -f $Script:Cfg.inference_device)
        Write-Host ('訓練裝置：{0}' -f $Script:Cfg.training_device)
        Write-Host ('推論結果：{0}' -f (Resolve-ConfiguredPath ([string]$Script:Cfg.demo_recon_root)))
        Write-Host ('訓練結果：{0}' -f (Resolve-ConfiguredPath ([string]$Script:Cfg.train_progress_root)))
        Write-Host ''
        Write-Host '1. 執行 native 第一次啟動自動初始化'
        Write-Host '2. 使用封包內示範影像做推論（demo / smoke）'
        Write-Host '3. 使用你自己的資料夾或單張影像做推論（外部驗證）'
        Write-Host '4. 執行基於歷史 R26 baseline 的完整重新訓練'
        Write-Host '5. 顯示環境檢查結果'
        Write-Host '6. 顯示目前啟動器設定'
        Write-Host '0. 離開'
        $choice = Read-Host '請選擇'

        switch ($choice) {
            '1' {
                Invoke-FirstRun
                $Script:Cfg = Get-LauncherConfig
            }
            '2' { Start-DemoInference }
            '3' { Start-CustomInference }
            '4' { Start-FullTrain }
            '5' { Show-Doctor }
            '6' { Show-Config }
            '0' { return }
            default { Write-Host ('未知選項：{0}' -f $choice) }
        }
    }
}

$Script:Cfg = Get-LauncherConfig

try {
    switch ($Action) {
        'menu' { Show-Menu }
        'help' { Show-Help }
        'show-config' { Show-Config }
        'save-config' { Save-CurrentConfig }
        'first-run' { Invoke-FirstRun }
        'doctor' { Show-Doctor }
        'infer-demo' { Start-DemoInference }
        'infer-custom' { Start-CustomInference -HostInputDir $InputDir }
        'train-full' { Start-FullTrain }
    }
}
catch {
    Write-Host ''
    Write-Host ('[錯誤] {0}' -f $_.Exception.Message)
    exit 1
}
