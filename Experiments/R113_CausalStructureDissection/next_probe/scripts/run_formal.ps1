$ErrorActionPreference = 'Stop'
if ($env:R113_CONFIRM_FORMAL -ne 'YES') {
    throw 'Formal training is blocked. Set R113_CONFIRM_FORMAL=YES only after explicit authorization.'
}
$Python = python
& $Python (Join-Path $PSScriptRoot 'run_probe.py') --mode formal --arm bounded_detail_supervised --confirm-formal

