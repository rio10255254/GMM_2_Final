# >>> portable-agent-env >>>
function Get-CodexHelperPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Leaf
    )

    $scriptsRoot = Join-Path $env:USERPROFILE '.portable-agent-env\scripts'
    return Join-Path $scriptsRoot $Leaf
}

function Invoke-CodexPinnedHome {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodexHome,

        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $invokeScript = Get-CodexHelperPath -Leaf 'Invoke-CodexWithHome.ps1'

    if (-not (Test-Path -LiteralPath $invokeScript)) {
        throw "Codex home wrapper not found: $invokeScript"
    }

    & $invokeScript -CodexHome $CodexHome -RawArgs $Args
}

function codex {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $yunyiHome = Join-Path $env:USERPROFILE '.codex-yunyi'
    Invoke-CodexPinnedHome -CodexHome $yunyiHome -Args $Args
}

function codex-yunyi {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $yunyiHome = Join-Path $env:USERPROFILE '.codex-yunyi'
    Invoke-CodexPinnedHome -CodexHome $yunyiHome -Args $Args
}

function codex-openai {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $openaiHome = Join-Path $env:USERPROFILE '.codex'
    Invoke-CodexPinnedHome -CodexHome $openaiHome -Args $Args
}

function codex-status {
    $statusScript = Get-CodexHelperPath -Leaf 'Get-CodexHomeStatus.ps1'
    if (-not (Test-Path -LiteralPath $statusScript)) {
        throw "Codex status helper not found: $statusScript"
    }

    $openaiHome = Join-Path $env:USERPROFILE '.codex'
    $yunyiHome = Join-Path $env:USERPROFILE '.codex-yunyi'

    Write-Host 'default terminal codex -> yunyi' -ForegroundColor Cyan
    & $statusScript -CodexHome $yunyiHome | Format-List
    & $statusScript -CodexHome $openaiHome | Format-List
}
# <<< portable-agent-env <<<
