param(
    [int]$Tail = 80
)

$ErrorActionPreference = "Stop"

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentDir = Split-Path -Parent $ScriptPath
$LogRoot = Join-Path $ExperimentDir "logs"

if (-not (Test-Path -LiteralPath $LogRoot)) {
    throw "V41-Standalone log folder not found: $LogRoot"
}

$ProcessRecord = Get-ChildItem -LiteralPath $LogRoot -Filter "*process.json" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $ProcessRecord) {
    throw "No V41-Standalone process record found under: $LogRoot"
}

$Info = Get-Content -LiteralPath $ProcessRecord.FullName | ConvertFrom-Json
$Proc = Get-Process -Id $Info.pid -ErrorAction SilentlyContinue

[ordered]@{
    process_record = $ProcessRecord.FullName
    pid = $Info.pid
    running = [bool]$Proc
    started_at = $Info.started_at
    run_suffix = $Info.run_suffix
    stdout = $Info.stdout
    stderr = $Info.stderr
} | ConvertTo-Json -Depth 3

Write-Output ""
Write-Output "--- stdout tail ---"
if (Test-Path -LiteralPath $Info.stdout) {
    Get-Content -LiteralPath $Info.stdout -Tail $Tail
} else {
    Write-Output "stdout file not found"
}

Write-Output ""
Write-Output "--- stderr tail ---"
if ((Test-Path -LiteralPath $Info.stderr) -and ((Get-Item -LiteralPath $Info.stderr).Length -gt 0)) {
    Get-Content -LiteralPath $Info.stderr -Tail $Tail
} else {
    Write-Output "stderr empty"
}
