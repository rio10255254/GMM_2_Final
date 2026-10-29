$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ErrorActionPreference = "Stop"

$script = "$ProjectRoot\Tools\Displacement_Algorithms\scripts\run_phase_newdata.py"

python $script `
  --roots "$ProjectRoot\20260704_20x" "$ProjectRoot\20260704_5x" `
  --output-root "$ProjectRoot\20260704_phase_dft_analysis" `
  --select-roi `
  --reference both `
  --upsample-factor 100
