$ErrorActionPreference = "Stop"
$ExperimentRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = python
$Runner = Join-Path $ExperimentRoot "scripts\run_r80.py"

Set-Location $ExperimentRoot
& $Python -u $Runner --stage all
if ($LASTEXITCODE -ne 0) {
    throw "R80 validation failed with exit code $LASTEXITCODE"
}
