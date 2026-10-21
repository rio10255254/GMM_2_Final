param([string]$RunId = 'r109_formal_scratch_continuous_b8_20260826', [int]$Epochs = 48, [int]$DetectorEpochs = 6, [int]$BatchSize = 8, [int]$Workers = 4)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& 'C:\Users\Rio\anaconda3\python.exe' (Join-Path $root 'training\train.py') --run-id $RunId --epochs $Epochs --detector-epochs $DetectorEpochs --batch-size $BatchSize --workers $Workers --no-amp
exit $LASTEXITCODE
