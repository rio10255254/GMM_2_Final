function Run_Thesis_3Mag_EdgePhase_SmokeTest()
% Smoke test for the thesis 3-magnification edge-phase MATLAB launcher.

scriptDir = fileparts(mfilename('fullpath'));
toolDir = fileparts(scriptDir);
outputRoot = fullfile(toolDir, 'tests', 'thesis_3mag_edge_phase_smoketest');
if exist(outputRoot, 'dir') == 7
    rmdir(outputRoot, 's');
end

Run_Thesis_3Mag_EdgePhase_SelectROI( ...
    'outputRoot', outputRoot, ...
    'autoRoi', [560, 80, 320, 320], ...
    'maxCases', 1, ...
    'showFigures', false);

summaryPath = fullfile(outputRoot, 'final_tables', 'edge_phase_summary.csv');
manifestPath = fullfile(outputRoot, 'source_manifest', 'run_manifest.json');
assert(exist(summaryPath, 'file') == 2, 'Missing summary CSV.');
assert(exist(manifestPath, 'file') == 2, 'Missing run manifest JSON.');

summaryTable = readtable(summaryPath, 'VariableNamingRule', 'preserve');
assert(height(summaryTable) == 1, 'Smoke test should run exactly one case.');
assert(summaryTable.valid_step_count > 0, 'Smoke test produced no valid displacement steps.');
end
