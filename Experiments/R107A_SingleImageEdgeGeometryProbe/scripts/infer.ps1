param(
    [Parameter(Mandatory=$true)][string]$Checkpoint,
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [int]$CoreSize = 512,
    [int]$Halo = 96
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = python
& $python (Join-Path $root 'inference\run_folder.py') --checkpoint $Checkpoint --input $InputPath --output $OutputPath --core-size $CoreSize --halo $Halo
exit $LASTEXITCODE

