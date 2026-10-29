param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = python
$Config = Join-Path $Root "config\experiment.json"
$Data = Join-Path $Root "data\continuous_pairs.npz"
$Summary = Join-Path $Root "results\comparison_summary.json"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Required Python runtime was not found."
}
if ((Test-Path -LiteralPath $Summary) -and -not $Force) {
    throw "A completed comparison already exists. Use -Force only after preserving the prior run."
}

if (-not (Test-Path -LiteralPath $Data)) {
    & $Python (Join-Path $Root "data\generate_continuous_dataset.py") --config $Config
    if ($LASTEXITCODE -ne 0) { throw "Dataset generation failed." }
}

& $Python (Join-Path $Root "training\run_short_ablation.py") --config $Config
if ($LASTEXITCODE -ne 0) { throw "A/B/C training failed." }

& $Python (Join-Path $Root "evaluation\evaluate_short_ablation.py") --config $Config
if ($LASTEXITCODE -ne 0) { throw "A/B/C evaluation failed." }

Write-Host "R101 short A/B/C experiment completed." -ForegroundColor Green
Write-Host $Summary

