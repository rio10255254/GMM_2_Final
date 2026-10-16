param(
    [ValidateSet('menu', 'help', 'show-config', 'save-config', 'first-run', 'doctor', 'infer-demo', 'infer-custom', 'train-quick', 'train-full', 'shell')]
    [string]$Action = 'menu',
    [string]$InputDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$NativeLauncher = Join-Path $ScriptRoot 'GeoEdge_NativeLauncher.ps1'
$DockerLauncher = Join-Path $ScriptRoot 'GeoEdge_Launcher.ps1'
$PortableRuntimeRoot = Join-Path $ScriptRoot 'portable_runtime'
$PortableRuntimeArchive = Join-Path $ScriptRoot 'portable_runtime_bundle.zip'
$BundledVenvPython = Join-Path $ScriptRoot '.venv\Scripts\python.exe'

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

function Get-ActionLabel {
    switch ($Action) {
        'menu' { return '開啟主選單' }
        'first-run' { return '第一次啟動初始化' }
        'doctor' { return '環境檢查' }
        'infer-demo' { return '示範資料推論' }
        'infer-custom' { return '外部資料 / 單張影像推論' }
        'train-quick' { return '快速訓練 smoke test' }
        'train-full' { return '完整訓練' }
        'shell' { return '開啟容器 shell' }
        default { return $Action }
    }
}

function Test-UsablePython {
    if (Test-LocalWindowsPython) {
        return $true
    }
    if (Test-BundledVenvPython) {
        return $true
    }
    return ((Test-Path -LiteralPath (Join-Path $PortableRuntimeRoot 'python.exe')) -or (Test-Path -LiteralPath $PortableRuntimeArchive))
}

function Test-LocalWindowsPython {
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($path in (Get-CommandSourcePaths -Name 'python')) {
        Add-UniqueString -List $candidates -Value $path
    }
    foreach ($path in (Get-PyLauncherInstalledPythonPaths)) {
        Add-UniqueString -List $candidates -Value $path
    }
    foreach ($path in (Get-CommonPythonInstallPaths)) {
        Add-UniqueString -List $candidates -Value $path
    }

    foreach ($pythonPath in $candidates) {
        try {
            & $pythonPath --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $true
            }
        }
        catch {
            continue
        }
    }
    return $false
}

function Test-BundledVenvPython {
    if (-not (Test-Path -LiteralPath $BundledVenvPython)) {
        return $false
    }

    & $BundledVenvPython --version *> $null
    return ($LASTEXITCODE -eq 0)
}

function Get-TargetLauncher {
    if ($Action -eq 'shell') {
        return [pscustomobject]@{
            path = $DockerLauncher
            route = 'docker'
        }
    }

    if (Test-UsablePython) {
        return [pscustomobject]@{
            path = $NativeLauncher
            route = 'native'
        }
    }

    return [pscustomobject]@{
        path = $DockerLauncher
        route = 'docker'
    }
}

$target = Get-TargetLauncher
Write-Host ('[AUTO] route={0}' -f $target.route)
Write-Host ('[AUTO] action={0}' -f (Get-ActionLabel))
if ($target.route -eq 'native') {
    if (Test-LocalWindowsPython) {
        Write-Host '[AUTO] reason=偵測到本機 Windows Python'
    }
    elseif (Test-BundledVenvPython) {
        Write-Host '[AUTO] reason=偵測到主包本地 .venv'
    }
    elseif ((Test-Path -LiteralPath (Join-Path $PortableRuntimeRoot 'python.exe')) -or (Test-Path -LiteralPath $PortableRuntimeArchive)) {
        Write-Host '[AUTO] reason=偵測到獨立 GPU runtime'
    }
    else {
        Write-Host '[AUTO] reason=偵測到可用的 Python runtime'
    }
}
else {
    Write-Host '[AUTO] reason=本機 Python / .venv 不可用，改走 Docker/WSL'
}
Write-Host ''

$args = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $target.path,
    '-Action', $Action
)
if ($InputDir) {
    $args += @('-InputDir', $InputDir)
}

& powershell.exe @args
exit $LASTEXITCODE
