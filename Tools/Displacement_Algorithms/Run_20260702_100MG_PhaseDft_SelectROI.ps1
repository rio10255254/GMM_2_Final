$ErrorActionPreference = "Stop"

$script = "D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts\run_phase_newdata.py"

python $script `
  --roots "D:\GMM_2_Final\20260702_100MG_位移" `
  --output-root "D:\GMM_2_Final\20260702_100MG_phase_dft_analysis" `
  --select-roi `
  --reference both `
  --upsample-factor 100
