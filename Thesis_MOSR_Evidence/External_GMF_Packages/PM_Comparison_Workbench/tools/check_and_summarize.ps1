$ErrorActionPreference = 'Stop'

$package = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\Rio\anaconda3\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python runtime not found: $python"
}

& $python (Join-Path $package 'tools\verify_bundle.py')
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python (Join-Path $package 'tools\analyze_outputs.py')
exit $LASTEXITCODE
