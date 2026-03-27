function test_candidate_flow_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(lab_root, 'scripts');

addpath(scripts_dir);

output_root = fullfile(lab_root, 'outputs', 'candidate_smoke');
summary = HDR_fitting_2D_WholeFOV_candidate_prealign( ...
    'subset_indices', [1], ...
    'output_root', output_root, ...
    'pre_alignment', true, ...
    'lock_tilt', true, ...
    'warm_start', true);

assert(isfile(fullfile(output_root, 'batch_results.csv')), 'Candidate flow should write batch_results.csv.');
assert(isfile(fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat')), 'Candidate flow should write PSF_fitted_2D_FOVstack.mat.');
assert(isfile(fullfile(output_root, 'candidate_config.json')), 'Candidate flow should write candidate_config.json.');
config = jsondecode(fileread(fullfile(output_root, 'candidate_config.json')));
assert(isfield(config, 'prealign_search_step') && abs(config.prealign_search_step - 0.25) < 1e-9, ...
    'Candidate flow should default to refined prealign_search_step = 0.25.');
assert(summary.num_images == 1, 'Candidate smoke run should process one image.');
end
