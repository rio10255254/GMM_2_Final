param([string]$RunId = 'r109_smoke_detector_renderer', [int]$StepsPerStage = 2)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& python (Join-Path $root 'training\train.py') --run-id $RunId --epochs 2 --detector-epochs 1 --batch-size 4 --workers 0 --data-limit 32 --validation-limit 32 --smoke-steps $StepsPerStage --no-amp
exit $LASTEXITCODE
