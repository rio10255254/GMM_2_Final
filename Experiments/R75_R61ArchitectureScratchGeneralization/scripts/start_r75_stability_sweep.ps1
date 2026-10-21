param(
    [string]$Device = "cuda:0",
    [int]$Epochs = 100
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "start_r75_formal_training.ps1"
$Seeds = @(750031, 750032, 750033)

foreach ($Seed in $Seeds) {
    & $Runner -Device $Device -Seed $Seed -Epochs $Epochs
    if ($LASTEXITCODE -ne 0) {
        throw "R75 stopped after seed $Seed failed."
    }
}
