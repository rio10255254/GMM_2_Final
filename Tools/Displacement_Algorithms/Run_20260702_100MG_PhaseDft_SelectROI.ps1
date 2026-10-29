$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ErrorActionPreference = "Stop"

$script = "$ProjectRoot\Tools\Displacement_Algorithms\scripts\run_phase_newdata.py"

python $script `
  --roots "$ProjectRoot\20260702_100MG_位移" `
  --output-root "$ProjectRoot\20260702_100MG_phase_dft_analysis" `
  --select-roi `
  --reference both `
  --upsample-factor 100
