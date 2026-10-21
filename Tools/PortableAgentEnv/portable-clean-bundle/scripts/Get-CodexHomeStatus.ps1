param(
    [Parameter(Mandatory = $true)]
    [string]$CodexHome
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$homePath = [System.IO.Path]::GetFullPath($CodexHome)
$configPath = Join-Path $homePath "config.toml"
$authPath = Join-Path $homePath "auth.json"

$modelProvider = ""
$authMode = ""

if (Test-Path -LiteralPath $configPath) {
    foreach ($line in Get-Content -LiteralPath $configPath -Encoding UTF8) {
        if ($line -match '^\s*model_provider\s*=\s*"([^"]+)"') {
            $modelProvider = $matches[1]
            break
        }
    }
}

if (Test-Path -LiteralPath $authPath) {
    try {
        $auth = Get-Content -LiteralPath $authPath -Encoding UTF8 | ConvertFrom-Json
        $authMode = [string]$auth.auth_mode
    } catch {
        $authMode = "unreadable"
    }
}

[pscustomobject]@{
    codex_home = $homePath
    config_exists = Test-Path -LiteralPath $configPath
    auth_exists = Test-Path -LiteralPath $authPath
    model_provider = $modelProvider
    auth_mode = $authMode
}
