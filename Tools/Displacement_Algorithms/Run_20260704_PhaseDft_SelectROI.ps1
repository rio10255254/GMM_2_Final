$ErrorActionPreference = "Stop"

$script = "D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts\run_phase_newdata.py"

python $script `
  --roots "D:\GMM_2_Final\20260704_20x" "D:\GMM_2_Final\20260704_5x" `
  --output-root "D:\GMM_2_Final\20260704_phase_dft_analysis" `
  --select-roi `
  --reference both `
  --upsample-factor 100
