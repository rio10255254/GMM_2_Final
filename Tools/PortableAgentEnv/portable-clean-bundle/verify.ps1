param(
    [string]$InstallRoot = "",
    [string]$CodexHome = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $InstallRoot = Join-Path $env:USERPROFILE ".portable-agent-env"
}

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Join-Path $env:USERPROFILE ".codex"
}

$ScriptsRoot = Join-Path $InstallRoot "scripts"
$HelperPath = Join-Path $ScriptsRoot "codex_resume_all.ps1"
$InvokeHelperPath = Join-Path $ScriptsRoot "Invoke-CodexWithHome.ps1"
$StatusHelperPath = Join-Path $ScriptsRoot "Get-CodexHomeStatus.ps1"
$EntrypointVerifierPath = Join-Path $ScriptsRoot "verify_codex_entrypoints.ps1"
$PwshProfile = Join-Path $env:USERPROFILE "Documents\PowerShell\Microsoft.PowerShell_profile.ps1"
$WindowsPowerShellProfile = Join-Path $env:USERPROFILE "Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"
$SkillPath = Join-Path $CodexHome "skills\portable-agent-env"
$AiTitleCache = Join-Path $CodexHome "session_ai_titles.jsonl"
$ConfigTemplate = Join-Path $CodexHome "config.portable.example.toml"
$ManifestPath = Join-Path $InstallRoot "manifest.json"
$ReadmePath = Join-Path $InstallRoot "docs\README_ENV_SETUP.md"

function Report-Item {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][bool]$Ok,
        [string]$Detail = ""
    )

    $status = if ($Ok) { "OK" } else { "MISSING" }
    if ([string]::IsNullOrWhiteSpace($Detail)) {
        Write-Host ("[{0}] {1}" -f $status, $Label)
    } else {
        Write-Host ("[{0}] {1} :: {2}" -f $status, $Label, $Detail)
    }
}

function Profile-ContainsMarker {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8).Contains("# >>> portable-agent-env >>>")
}

Write-Host ""
Write-Host "Portable Agent Environment Verification"
Write-Host ""

Report-Item -Label "Install root" -Ok (Test-Path -LiteralPath $InstallRoot) -Detail $InstallRoot
Report-Item -Label "Scripts root" -Ok (Test-Path -LiteralPath $ScriptsRoot) -Detail $ScriptsRoot
Report-Item -Label "Helper script" -Ok (Test-Path -LiteralPath $HelperPath) -Detail $HelperPath
Report-Item -Label "Invoke wrapper" -Ok (Test-Path -LiteralPath $InvokeHelperPath) -Detail $InvokeHelperPath
Report-Item -Label "Status helper" -Ok (Test-Path -LiteralPath $StatusHelperPath) -Detail $StatusHelperPath
Report-Item -Label "Entrypoint verifier" -Ok (Test-Path -LiteralPath $EntrypointVerifierPath) -Detail $EntrypointVerifierPath
Report-Item -Label "Manifest" -Ok (Test-Path -LiteralPath $ManifestPath) -Detail $ManifestPath
Report-Item -Label "README" -Ok (Test-Path -LiteralPath $ReadmePath) -Detail $ReadmePath
Report-Item -Label "pwsh profile wrapper" -Ok (Profile-ContainsMarker -Path $PwshProfile) -Detail $PwshProfile
Report-Item -Label "Windows PowerShell profile wrapper" -Ok (Profile-ContainsMarker -Path $WindowsPowerShellProfile) -Detail $WindowsPowerShellProfile
Report-Item -Label "Installed skill" -Ok (Test-Path -LiteralPath $SkillPath) -Detail $SkillPath
Report-Item -Label "Config template" -Ok (Test-Path -LiteralPath $ConfigTemplate) -Detail $ConfigTemplate

if (Test-Path -LiteralPath $AiTitleCache) {
    $count = (Get-Content -LiteralPath $AiTitleCache -Encoding UTF8 | Measure-Object -Line).Lines
    Report-Item -Label "AI title cache" -Ok $true -Detail "$AiTitleCache ($count lines)"
} else {
    Report-Item -Label "AI title cache" -Ok $false -Detail $AiTitleCache
}

$pwshCommand = "Get-Command codex | Select-Object Name, CommandType, Source | ConvertTo-Json -Compress"
$powershellCommand = 'Get-Command codex | Select-Object Name, CommandType, Source | ConvertTo-Json -Compress'

try {
    $pwshResult = pwsh -Command $pwshCommand
    Report-Item -Label "pwsh codex resolution" -Ok $true -Detail $pwshResult
} catch {
    Report-Item -Label "pwsh codex resolution" -Ok $false -Detail $_.Exception.Message
}

try {
    $powershellResult = powershell -Command $powershellCommand
    Report-Item -Label "powershell codex resolution" -Ok $true -Detail $powershellResult
} catch {
    Report-Item -Label "powershell codex resolution" -Ok $false -Detail $_.Exception.Message
}

try {
    & $EntrypointVerifierPath *> $null
    Report-Item -Label "Entrypoint smoke tests" -Ok $true -Detail $EntrypointVerifierPath
} catch {
    Report-Item -Label "Entrypoint smoke tests" -Ok $false -Detail $_.Exception.Message
}

Write-Host ""
Write-Host "Verify complete."
