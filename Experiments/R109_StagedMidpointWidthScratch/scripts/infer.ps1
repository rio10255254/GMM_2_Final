param([Parameter(Mandatory=$true)][string]$Checkpoint,[Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$OutputPath,[int]$Core=1024,[int]$Halo=192)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot
& 'C:\Users\Rio\anaconda3\python.exe' (Join-Path $root 'inference\run_folder.py') --checkpoint $Checkpoint --input $InputPath --output $OutputPath --core $Core --halo $Halo
exit $LASTEXITCODE
