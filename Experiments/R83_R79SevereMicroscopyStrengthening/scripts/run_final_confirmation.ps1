$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ErrorActionPreference = 'Stop'
$ExperimentRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = python
$MatlabExe = 'C:\Program Files\MATLAB\R2025b\bin\matlab.exe'
$R82Scripts = (Join-Path $ProjectRoot 'Experiments\R82_R39R40CrossSceneGeneralizationBenchmark\scripts')
$LocalScripts = Join-Path $ExperimentRoot 'scripts'
$OutputRoot = Join-Path $ExperimentRoot 'results\final_confirmation'

& $PythonExe (Join-Path $ExperimentRoot 'scripts\prepare_final_confirmation.py')
if ($LASTEXITCODE -ne 0) { throw 'Final confirmation reconstruction failed.' }
$Synthetic = (Join-Path $OutputRoot 'locked_synthetic_acm').Replace('\','/')
$R73 = (Join-Path $OutputRoot 'development_recheck\R73_novel_shapes').Replace('\','/')
$R74 = (Join-Path $OutputRoot 'development_recheck\R74_hard_microscopy').Replace('\','/')
$SEM = (Join-Path $OutputRoot 'SEM_reserved').Replace('\','/')
$ExternalScripts = $R82Scripts.Replace('\','/')
$SelectedScripts = $LocalScripts.Replace('\','/')
$Batch = "addpath('$ExternalScripts'); addpath('$SelectedScripts'); run_acm_multimethod('$Synthetic'); run_acm_multimethod('$R73'); run_acm_multimethod('$R74'); run_sem_acm_selected_pillars('$SEM');"
& $MatlabExe -batch $Batch
if ($LASTEXITCODE -ne 0) { throw 'Final ACM confirmation failed.' }
& $PythonExe (Join-Path $ExperimentRoot 'scripts\evaluate_final_real_motion.py')
if ($LASTEXITCODE -ne 0) { throw 'Final real-FOV motion confirmation failed.' }
& $PythonExe (Join-Path $ExperimentRoot 'scripts\analyze_final_confirmation.py')
exit $LASTEXITCODE
