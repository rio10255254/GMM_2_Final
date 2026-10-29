$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ErrorActionPreference = 'Stop'
$ExperimentRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PythonExe = python
$MatlabExe = 'C:\Program Files\MATLAB\R2025b\bin\matlab.exe'
$R82Scripts = (Join-Path $ProjectRoot 'Experiments\R82_R39R40CrossSceneGeneralizationBenchmark\scripts')
$LocalScripts = Join-Path $ExperimentRoot 'scripts'
$ScreenRoot = Join-Path $ExperimentRoot 'results\formal_checkpoint_screen'

& $PythonExe (Join-Path $ExperimentRoot 'scripts\prepare_formal_checkpoint_screen.py')
if ($LASTEXITCODE -ne 0) { throw 'Formal checkpoint reconstruction failed.' }
$R73 = (Join-Path $ScreenRoot 'R73_novel_shapes').Replace('\','/')
$R74 = (Join-Path $ScreenRoot 'R74_hard_microscopy').Replace('\','/')
$SEM = (Join-Path $ScreenRoot 'SEM').Replace('\','/')
$ExternalScripts = $R82Scripts.Replace('\','/')
$SelectedScripts = $LocalScripts.Replace('\','/')
$Batch = "addpath('$ExternalScripts'); addpath('$SelectedScripts'); run_acm_multimethod('$R73'); run_acm_multimethod('$R74'); run_sem_acm_selected_pillars('$SEM');"
& $MatlabExe -batch $Batch
if ($LASTEXITCODE -ne 0) { throw 'Formal checkpoint ACM screen failed.' }
& $PythonExe (Join-Path $ExperimentRoot 'scripts\analyze_formal_checkpoint_screen.py')
exit $LASTEXITCODE
