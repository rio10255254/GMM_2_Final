function test_candidate_flow_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');

output_root = fullfile(lab_root, 'outputs', 'candidate_smoke');
assert(isfile(fullfile(output_root, 'batch_results.csv')), 'Candidate flow should write batch_results.csv.');
assert(isfile(fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat')), 'Candidate flow should write PSF_fitted_2D_FOVstack.mat.');
assert(isfile(fullfile(output_root, 'candidate_config.json')), 'Candidate flow should write candidate_config.json.');
config = jsondecode(fileread(fullfile(output_root, 'candidate_config.json')));
assert(isfield(config, 'prealign_search_step') && abs(config.prealign_search_step - 0.25) < 1e-9, ...
    'Candidate flow should default to refined prealign_search_step = 0.25.');
tbl = readtable(fullfile(output_root, 'batch_results.csv'), TextType = "string");
assert(height(tbl) == 1, 'Candidate smoke fixture should preserve a one-image batch result.');
end
