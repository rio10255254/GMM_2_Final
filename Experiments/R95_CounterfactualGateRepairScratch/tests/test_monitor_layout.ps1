$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Monitor = Join-Path $Root "scripts\monitor_training.ps1"
$Widths = @(44, 60, 84, 108)

foreach ($Width in $Widths) {
    $Output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Monitor `
        -Once -NoClear -WidthOverride $Width -HeightOverride 18 6>&1 | Out-String
    $Lines = @($Output -split "`r?`n" | Where-Object { $_.Length -gt 0 })
    if ($Lines.Count -lt 6) { throw "Width $Width produced an incomplete dashboard" }
    $Longest = ($Lines | Measure-Object -Property Length -Maximum).Maximum
    if ($Longest -gt $Width) { throw "Width $Width wrapped or overflowed to $Longest characters" }
    if ($Output -match "[-=]{12,}") { throw "Width $Width still contains a long separator rule" }
    foreach ($Required in @("R95", "GPU", "LAST", "HEALTH")) {
        if ($Output -notmatch [Regex]::Escape($Required)) { throw "Width $Width is missing $Required" }
    }
}

Write-Host "R95 monitor layout passed at widths: $($Widths -join ', ')" -ForegroundColor Green
