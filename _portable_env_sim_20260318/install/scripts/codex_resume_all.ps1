param(
    [string]$CodexCommand = "",

    [string]$CodexHome = "",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RawArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    $CodexHome = Join-Path $env:USERPROFILE ".codex"
}

if ([string]::IsNullOrWhiteSpace($CodexCommand)) {
    $resolved = Get-Command codex.cmd -ErrorAction Stop
    $CodexCommand = $resolved.Source
}

$sessionsRoot = Join-Path $CodexHome "sessions"
$sessionIndexPath = Join-Path $CodexHome "session_index.jsonl"
$historyPath = Join-Path $CodexHome "history.jsonl"
$aiTitleCachePath = Join-Path $CodexHome "session_ai_titles.jsonl"

$forwardArgs = @()
$seenResume = $false
foreach ($arg in $RawArgs) {
    if (-not $seenResume -and $arg -eq "resume") {
        $seenResume = $true
        continue
    }
    if ($arg -eq "--all") {
        continue
    }
    if ($arg -eq "--last") {
        continue
    }
    $forwardArgs += $arg
}

if (-not (Test-Path -LiteralPath $sessionsRoot)) {
    Write-Host ""
    Write-Host "No on-disk Codex sessions found yet." -ForegroundColor Yellow
    Write-Host "Falling back to native Codex resume picker." -ForegroundColor Yellow
    & $CodexCommand resume --all @forwardArgs
    exit $LASTEXITCODE
}

function Preview-Text {
    param(
        [AllowEmptyString()]
        [string]$Text,

        [int]$Limit = 72
    )

    $cleaned = (($Text -replace "\s+", " ").Trim())
    if ($cleaned.Length -le $Limit) {
        return $cleaned
    }
    return $cleaned.Substring(0, [Math]::Max(0, $Limit - 3)) + "..."
}

function Coalesce-String {
    param(
        [AllowNull()]
        [object[]]$Values
    )

    foreach ($value in $Values) {
        if ($null -ne $value) {
            return [string]$value
        }
    }

    return ""
}

function Get-OptionalValue {
    param(
        [AllowNull()]
        [object]$Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) {
            return $Object[$Name]
        }
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) {
        return $property.Value
    }

    return $null
}

function Get-ContentText {
    param(
        [AllowNull()]
        [object]$Content
    )

    if ($null -eq $Content) {
        return ""
    }

    if ($Content -is [string]) {
        return [string]$Content
    }

    foreach ($item in $Content) {
        $itemType = Coalesce-String @((Get-OptionalValue -Object $item -Name "type"))
        if ($itemType -in @("input_text", "output_text", "text")) {
            $text = Coalesce-String @((Get-OptionalValue -Object $item -Name "text"))
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                return $text
            }
        }
    }

    return ""
}

function Test-NoisePrompt {
    param(
        [AllowEmptyString()]
        [string]$Text
    )

    $normalized = ((Coalesce-String @($Text)) -replace "\s+", " ").Trim()
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return $true
    }

    $prefixes = @(
        "<environment_context>",
        "# AGENTS.md instructions",
        "<model_switch>",
        "<permissions instructions>",
        "<collaboration_mode>",
        "<skills_instructions>",
        "<turn_aborted>"
    )

    foreach ($prefix in $prefixes) {
        if ($normalized.StartsWith($prefix)) {
            return $true
        }
    }

    return $false
}

function Get-SessionSignals {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $lastTimestamp = $null
    $firstUserText = ""

    foreach ($raw in Get-Content -LiteralPath $Path -Encoding UTF8) {
        try {
            $payload = $raw | ConvertFrom-Json
        } catch {
            continue
        }

        $timestampText = Coalesce-String @((Get-OptionalValue -Object $payload -Name "timestamp"))
        if (-not [string]::IsNullOrWhiteSpace($timestampText)) {
            try {
                $parsed = [datetime]::Parse($timestampText)
                if ($null -eq $lastTimestamp -or $parsed -gt $lastTimestamp) {
                    $lastTimestamp = $parsed
                }
            } catch {
            }
        }

        if (-not [string]::IsNullOrWhiteSpace($firstUserText)) {
            continue
        }

        $type = Coalesce-String @((Get-OptionalValue -Object $payload -Name "type"))
        if ($type -eq "response_item") {
            $inner = Get-OptionalValue -Object $payload -Name "payload"
            $innerType = Coalesce-String @((Get-OptionalValue -Object $inner -Name "type"))
            $role = Coalesce-String @((Get-OptionalValue -Object $inner -Name "role"))
            if ($innerType -eq "message" -and $role -eq "user") {
                $contentText = Get-ContentText -Content (Get-OptionalValue -Object $inner -Name "content")
                if (-not (Test-NoisePrompt -Text $contentText)) {
                    $firstUserText = $contentText
                }
            }
        } elseif ($type -eq "event_msg") {
            $inner = Get-OptionalValue -Object $payload -Name "payload"
            $innerType = Coalesce-String @((Get-OptionalValue -Object $inner -Name "type"))
            if ($innerType -eq "user_message") {
                $messageText = Coalesce-String @((Get-OptionalValue -Object $inner -Name "message"))
                if (-not (Test-NoisePrompt -Text $messageText)) {
                    $firstUserText = $messageText
                }
            }
        }
    }

    return @{
        LastTimestamp = $lastTimestamp
        FirstUserText = $firstUserText
    }
}

function Normalize-Title {
    param(
        [string]$Title,
        [string]$Fallback
    )

    $value = ((Coalesce-String @($Title)) -replace "\s+", " ").Trim()
    if ($value.StartsWith("[TG]")) {
        $value = $value.Substring(4).Trim()
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = ((Coalesce-String @($Fallback)) -replace "\s+", " ").Trim()
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = "Untitled conversation"
    }
    return $value
}

function Load-Jsonl-LatestMap {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Builder
    )

    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $map
    }

    foreach ($raw in Get-Content -LiteralPath $Path -Encoding UTF8) {
        try {
            $payload = $raw | ConvertFrom-Json
        } catch {
            continue
        }

        $item = & $Builder $payload
        if ($null -eq $item) {
            continue
        }

        $key = [string]$item.Key
        if ([string]::IsNullOrWhiteSpace($key)) {
            continue
        }
        $map[$key] = $item.Value
    }

    return $map
}

function Append-Jsonl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [object]$Payload
    )

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory) -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
    }

    $line = $Payload | ConvertTo-Json -Depth 8 -Compress
    Add-Content -LiteralPath $Path -Value $line -Encoding UTF8
}

function Sanitize-AiTitle {
    param(
        [AllowEmptyString()]
        [string]$Text
    )

    $value = ((Coalesce-String @($Text)) -replace "\s+", " ").Trim()
    $value = $value.Trim('"', "'", ' ', '.', ',', [char]0x3002, [char]0xFF0C, [char]0x3001)
    if ($value.Length -gt 48) {
        $value = $value.Substring(0, 48).Trim()
    }
    return $value
}

function Invoke-CodexTitleBatch {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Items,

        [Parameter(Mandatory = $true)]
        [string]$CodexCommand
    )

    $payload = @(
        foreach ($item in $Items) {
            @{
                session_id = $item.SessionId
                current_title = $item.HeuristicTitle
                preview = Preview-Text -Text $item.PromptPreview -Limit 160
                source = $item.Source
                provider = $item.ModelProvider
                cwd = $item.Cwd
            }
        }
    ) | ConvertTo-Json -Depth 8 -Compress

    $prompt = @"
You are a conversation title generator.
For each session, create a short, clear, recognizable Chinese title.

Rules:
- Focus on the real task, not framework boilerplate
- Prefer about 8-20 Chinese characters when possible
- Do not add quotes, numbering, or trailing punctuation
- Each title must stand on its own
- Keep important terms like Codex, Docker, GMF, GeoEdge
- If the current title is already good, you may shorten it, but do not make it worse
- Output JSON only, with no extra text

Output format:
{"titles":[{"session_id":"...","title":"..."}]}

Data:
$payload
"@

    $lines = $prompt | & $CodexCommand exec --ephemeral --skip-git-repo-check --json - 2>$null
    $resultText = ""

    foreach ($line in $lines) {
        try {
            $event = $line | ConvertFrom-Json
        } catch {
            continue
        }

        if ((Coalesce-String @((Get-OptionalValue -Object $event -Name "type"))) -ne "item.completed") {
            continue
        }

        $item = Get-OptionalValue -Object $event -Name "item"
        if ((Coalesce-String @((Get-OptionalValue -Object $item -Name "type"))) -ne "agent_message") {
            continue
        }

        $resultText = Coalesce-String @((Get-OptionalValue -Object $item -Name "text"))
    }

    if ([string]::IsNullOrWhiteSpace($resultText)) {
        throw "AI title batch returned no result text."
    }

    try {
        return $resultText | ConvertFrom-Json
    } catch {
        throw "AI title batch returned invalid JSON: $resultText"
    }
}

$indexEntries = Load-Jsonl-LatestMap -Path $sessionIndexPath -Builder {
    param($payload)
    $id = Coalesce-String @($payload.id)
    if ([string]::IsNullOrWhiteSpace($id)) {
        return $null
    }
    return @{
        Key = $id
        Value = @{
            thread_name = Coalesce-String @($payload.thread_name)
            updated_at = Coalesce-String @($payload.updated_at)
        }
    }
}

$historyLatest = Load-Jsonl-LatestMap -Path $historyPath -Builder {
    param($payload)
    $sessionId = Coalesce-String @($payload.session_id)
    $text = Coalesce-String @($payload.text)
    if ([string]::IsNullOrWhiteSpace($sessionId) -or [string]::IsNullOrWhiteSpace($text)) {
        return $null
    }
    return @{
        Key = $sessionId
        Value = $text
    }
}

$pattern = [regex]'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|test-session)$'
$rows = foreach ($file in Get-ChildItem -Path $sessionsRoot -Recurse -File -Filter "rollout-*.jsonl") {
    $match = $pattern.Match($file.BaseName)
    if (-not $match.Success) {
        continue
    }

    $sessionId = $match.Groups[1].Value
    $meta = $null

    try {
        $firstLine = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -TotalCount 1
        if (-not [string]::IsNullOrWhiteSpace($firstLine)) {
            $parsed = $firstLine | ConvertFrom-Json
            if ($parsed.type -eq "session_meta" -and $parsed.payload) {
                $meta = $parsed.payload
            }
        }
    } catch {
        $meta = $null
    }

    $indexEntry = $indexEntries[$sessionId]
    $signals = Get-SessionSignals -Path $file.FullName
    $historyText = Coalesce-String @($historyLatest[$sessionId])
    $title = Normalize-Title `
        -Title (Coalesce-String @((Get-OptionalValue -Object $indexEntry -Name "thread_name"), (Get-OptionalValue -Object $meta -Name "thread_name"))) `
        -Fallback (Normalize-Title -Title (Coalesce-String @((Get-OptionalValue -Object $signals -Name "FirstUserText"))) -Fallback (Preview-Text -Text $historyText))

    $source = Coalesce-String @((Get-OptionalValue -Object $meta -Name "source"))
    $originator = Coalesce-String @((Get-OptionalValue -Object $meta -Name "originator"))
    if ([string]::IsNullOrWhiteSpace($source) -and $originator -match "vscode") {
        $source = "vscode"
    } elseif ([string]::IsNullOrWhiteSpace($source) -and $originator -match "exec") {
        $source = "exec"
    } elseif ([string]::IsNullOrWhiteSpace($source) -and $originator -match "tui") {
        $source = "cli"
    }

    [pscustomobject]@{
        SessionId = $sessionId
        LastTime = if ($null -ne $signals.LastTimestamp) { $signals.LastTimestamp } else { $file.LastWriteTime }
        ModelProvider = Coalesce-String @((Get-OptionalValue -Object $meta -Name "model_provider"))
        Source = [string]$source
        Cwd = Coalesce-String @((Get-OptionalValue -Object $meta -Name "cwd"))
        HeuristicTitle = $title
        PromptPreview = Coalesce-String @((Get-OptionalValue -Object $signals -Name "FirstUserText"), $historyText, $title)
        DisplayTitle = $title
        FilePath = $file.FullName
    }
}

$aiTitleEntries = Load-Jsonl-LatestMap -Path $aiTitleCachePath -Builder {
    param($payload)
    $sessionId = Coalesce-String @($payload.session_id)
    $title = Coalesce-String @($payload.title)
    if ([string]::IsNullOrWhiteSpace($sessionId) -or [string]::IsNullOrWhiteSpace($title)) {
        return $null
    }
    return @{
        Key = $sessionId
        Value = @{
            title = $title
            generated_at = Coalesce-String @($payload.generated_at)
        }
    }
}

$pendingAiTitles = @($rows | Where-Object { -not $aiTitleEntries.ContainsKey($_.SessionId) })
if ($pendingAiTitles.Count -gt 0) {
    $batchSize = 15
    $batchCount = [Math]::Ceiling($pendingAiTitles.Count / $batchSize)
    Write-Host ""
    Write-Host ("Generating AI titles for {0} new sessions..." -f $pendingAiTitles.Count) -ForegroundColor Yellow

    for ($batchIndex = 0; $batchIndex -lt $batchCount; $batchIndex++) {
        $start = $batchIndex * $batchSize
        $count = [Math]::Min($batchSize, $pendingAiTitles.Count - $start)
        $batch = @($pendingAiTitles | Select-Object -Skip $start -First $count)
        Write-Host ("AI title batch {0}/{1}" -f ($batchIndex + 1), $batchCount) -ForegroundColor DarkYellow

        try {
            $result = Invoke-CodexTitleBatch -Items $batch -CodexCommand $CodexCommand
            $titles = @(Get-OptionalValue -Object $result -Name "titles")
            foreach ($item in $titles) {
                $sessionId = Coalesce-String @((Get-OptionalValue -Object $item -Name "session_id"))
                $title = Sanitize-AiTitle -Text (Coalesce-String @((Get-OptionalValue -Object $item -Name "title")))
                if ([string]::IsNullOrWhiteSpace($sessionId) -or [string]::IsNullOrWhiteSpace($title)) {
                    continue
                }

                Append-Jsonl -Path $aiTitleCachePath -Payload @{
                    session_id = $sessionId
                    title = $title
                    generated_at = [datetime]::UtcNow.ToString("o")
                }

                $aiTitleEntries[$sessionId] = @{
                    title = $title
                    generated_at = [datetime]::UtcNow.ToString("o")
                }
            }
        } catch {
            Write-Host ("AI title batch failed: {0}" -f $_.Exception.Message) -ForegroundColor Red
        }
    }
}

foreach ($row in $rows) {
    $aiEntry = $aiTitleEntries[$row.SessionId]
    if ($null -ne $aiEntry) {
        $cachedTitle = Sanitize-AiTitle -Text (Coalesce-String @((Get-OptionalValue -Object $aiEntry -Name "title")))
        if (-not [string]::IsNullOrWhiteSpace($cachedTitle)) {
            $row.DisplayTitle = $cachedTitle
        }
    }
}

$rows = $rows | Sort-Object LastTime -Descending

if (-not $rows -or $rows.Count -eq 0) {
    throw "No Codex sessions found under: $sessionsRoot"
}

Write-Host ""
Write-Host ("Full on-disk Codex sessions: {0}" -f $rows.Count) -ForegroundColor Cyan
Write-Host ("Source root: {0}" -f $sessionsRoot) -ForegroundColor DarkGray
Write-Host ""

$index = 1
foreach ($row in $rows) {
    $provider = if ([string]::IsNullOrWhiteSpace($row.ModelProvider)) { "-" } else { $row.ModelProvider }
    $source = if ([string]::IsNullOrWhiteSpace($row.Source)) { "-" } else { $row.Source }
    $title = Preview-Text -Text $row.DisplayTitle -Limit 88
    $timeText = $row.LastTime.ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host ("[{0}] {1} | {2} | {3} | {4}" -f $index, $timeText, $provider, $source, $title)
    $index++
}

Write-Host ""
$choice = Read-Host "Enter number or session id to resume (blank to cancel)"
if ([string]::IsNullOrWhiteSpace($choice)) {
    Write-Host "Canceled."
    exit 0
}

$selected = $null
if ($choice -match '^\d+$') {
    $number = [int]$choice
    if ($number -ge 1 -and $number -le $rows.Count) {
        $selected = $rows[$number - 1]
    }
} else {
    $exact = $rows | Where-Object { $_.SessionId -eq $choice } | Select-Object -First 1
    if ($exact) {
        $selected = $exact
    } else {
        $prefixMatches = @($rows | Where-Object { $_.SessionId.StartsWith($choice) })
        if ($prefixMatches.Count -eq 1) {
            $selected = $prefixMatches[0]
        }
    }
}

if ($null -eq $selected) {
    throw "Selection not found: $choice"
}

Write-Host ""
Write-Host ("Resuming session: {0}" -f $selected.SessionId) -ForegroundColor Green
Write-Host ("Title: {0}" -f $selected.DisplayTitle)
Write-Host ("Provider: {0}" -f $selected.ModelProvider)
Write-Host ("Source: {0}" -f $selected.Source)
Write-Host ("Cwd: {0}" -f $selected.Cwd)
Write-Host ""

& $CodexCommand resume $selected.SessionId @forwardArgs
