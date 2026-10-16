$ErrorActionPreference = "Stop"

$RepoRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence"
$Python = "C:\Users\Rio\anaconda3\python.exe"
$Launcher = Join-Path $RepoRoot "LabSystem_MOSR\Experiments\R55_SourceStyleRealisticTraining\scripts\launch_r55.py"

& $Python -u $Launcher `
  --candidate r55_source_style_r53_scratch `
  --num-epoch 50 `
  --batch-size 16 `
  --val-batch-size 4 `
  --num-workers 4 `
  --seq-batch-size 4 `
  --run-suffix formal_source_style_e050_b016_w04_nophys
