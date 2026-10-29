param(
    [int]$NafProcessId = 37568
)

$ErrorActionPreference = 'Stop'
$experiment = Split-Path -Parent $MyInvocation.MyCommand.Path
$nafSummary = Join-Path $experiment 'results\nafnet\training_summary.json'
$edsrOutput = Join-Path $experiment 'results\edsr'
$edsrSummary = Join-Path $edsrOutput 'training_summary.json'

if (Get-Process -Id $NafProcessId -ErrorAction SilentlyContinue) {
    Wait-Process -Id $NafProcessId
}

if (-not (Test-Path -LiteralPath $nafSummary)) {
    throw "NAFNet did not produce its completed training summary; EDSR was not started."
}
if (Test-Path -LiteralPath $edsrSummary) {
    exit 0
}

New-Item -ItemType Directory -Force -Path $edsrOutput | Out-Null
$python = python
$script = Join-Path $experiment 'train_modern_baseline.py'
$stdout = Join-Path $edsrOutput 'training_console.log'
$stderr = Join-Path $edsrOutput 'training_console.err.log'
$arguments = @(
    $script,
    '--model', 'edsr',
    '--epochs', '30',
    '--micro-batch-size', '32',
    '--effective-batch-size', '64',
    '--validate-every', '3',
    '--output', $edsrOutput
)
$process = Start-Process -FilePath $python -ArgumentList $arguments `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
    -WindowStyle Hidden -PassThru -Wait
if ($process.ExitCode -ne 0) {
    throw "EDSR training failed with exit code $($process.ExitCode)."
}
if (-not (Test-Path -LiteralPath $edsrSummary)) {
    throw 'EDSR process exited without a completed training summary.'
}
