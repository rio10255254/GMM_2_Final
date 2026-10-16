$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$python = 'C:\Users\Rio\anaconda3\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python runtime not found: $python"
}

& $python -m py_compile `
    (Join-Path $root 'model\r116_model.py') `
    (Join-Path $root 'inference\tiled.py') `
    (Join-Path $root 'training\losses.py') `
    (Join-Path $root 'training\dataset.py') `
    (Join-Path $root 'training\profile_targets.py') `
    (Join-Path $root 'training\smoke_train.py') `
    (Join-Path $root 'training\train.py') `
    (Join-Path $root 'data\prepare_dataset.py') `
    (Join-Path $root 'probes\r109_counterfactuals.py') `
    (Join-Path $root 'probes\analyze_counterfactuals.py') `
    (Join-Path $root 'probes\diagnose_formal_failure.py') `
    (Join-Path $root 'probes\stress_width_numerics.py') `
    (Join-Path $root 'validation\audit_and_select.py') `
    (Join-Path $root 'scripts\benchmark_training.py') `
    (Join-Path $root 'scripts\finalize_design.py')
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python -m pytest (Join-Path $root 'tests') -q
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python (Join-Path $root 'training\smoke_train.py') --device cpu --output-name architecture_smoke_cpu.json
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python (Join-Path $root 'scripts\finalize_design.py')
exit $LASTEXITCODE
