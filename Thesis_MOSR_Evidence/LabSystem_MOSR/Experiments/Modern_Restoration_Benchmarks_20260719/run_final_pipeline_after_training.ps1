param(
    [int]$EdsrLauncherProcessId = 36412
)

$ErrorActionPreference = 'Stop'
$experiment = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = 'C:\Users\Rio\anaconda3\python.exe'
$nafCheckpoint = Join-Path $experiment 'results\nafnet\best_nafnet.pth.tar'
$edsrCheckpoint = Join-Path $experiment 'results\edsr\best_edsr.pth.tar'
$pipelineLogs = Join-Path $experiment 'pipeline_logs'
New-Item -ItemType Directory -Force -Path $pipelineLogs | Out-Null

if (Get-Process -Id $EdsrLauncherProcessId -ErrorAction SilentlyContinue) {
    Wait-Process -Id $EdsrLauncherProcessId
}
if (-not (Test-Path -LiteralPath $nafCheckpoint)) {
    throw 'NAFNet checkpoint is missing after training.'
}
if (-not (Test-Path -LiteralPath $edsrCheckpoint)) {
    throw 'EDSR checkpoint is missing after training.'
}

function Invoke-PythonStage {
    param(
        [string]$Name,
        [string]$Script,
        [string[]]$Arguments
    )
    $stdout = Join-Path $pipelineLogs "$Name.log"
    $stderr = Join-Path $pipelineLogs "$Name.err.log"
    $allArguments = @($Script) + $Arguments
    $process = Start-Process -FilePath $python -ArgumentList $allArguments `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr `
        -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0) {
        throw "Pipeline stage '$Name' failed with exit code $($process.ExitCode)."
    }
}

Invoke-PythonStage -Name '01_infer_nafnet' `
    -Script (Join-Path $experiment 'infer_modern_baseline.py') `
    -Arguments @(
        '--checkpoint', $nafCheckpoint,
        '--output', (Join-Path $experiment 'results\nafnet\real_inference'),
        '--tile-size', '256', '--overlap', '128', '--tile-batch', '32'
    )

Invoke-PythonStage -Name '02_infer_edsr' `
    -Script (Join-Path $experiment 'infer_modern_baseline.py') `
    -Arguments @(
        '--checkpoint', $edsrCheckpoint,
        '--output', (Join-Path $experiment 'results\edsr\real_inference'),
        '--tile-size', '256', '--overlap', '128', '--tile-batch', '32'
    )

Invoke-PythonStage -Name '03_displacement' `
    -Script (Join-Path $experiment 'analyze_multimethod_displacement.py') `
    -Arguments @()

Invoke-PythonStage -Name '04_circular_cd_sharpness' `
    -Script (Join-Path $experiment 'analyze_circular_cd_sharpness.py') `
    -Arguments @()

Invoke-PythonStage -Name '05_line_analysis' `
    -Script (Join-Path $experiment 'analyze_line_multimethod.py') `
    -Arguments @()

Invoke-PythonStage -Name '06_export_images' `
    -Script (Join-Path $experiment 'export_method_crops.py') `
    -Arguments @()

Invoke-PythonStage -Name '07_runtime' `
    -Script (Join-Path $experiment 'benchmark_models.py') `
    -Arguments @('--patch-iterations', '50', '--full-iterations', '8')

$matlabScript = (Join-Path $experiment 'plot_benchmark_results.m').Replace('\', '/')
$matlabOut = Join-Path $pipelineLogs '08_matlab_figures.log'
$matlabErr = Join-Path $pipelineLogs '08_matlab_figures.err.log'
$matlab = Start-Process -FilePath 'matlab.exe' `
    -ArgumentList @('-batch', "run('$matlabScript')") `
    -RedirectStandardOutput $matlabOut -RedirectStandardError $matlabErr `
    -WindowStyle Hidden -PassThru -Wait
if ($matlab.ExitCode -ne 0) {
    throw "MATLAB figure generation failed with exit code $($matlab.ExitCode)."
}

Invoke-PythonStage -Name '09_final_validation' `
    -Script (Join-Path $experiment 'validate_final_benchmark.py') `
    -Arguments @()
