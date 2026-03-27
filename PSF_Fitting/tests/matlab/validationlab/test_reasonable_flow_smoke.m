function test_reasonable_flow_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');

output_root = fullfile(lab_root, 'outputs', 'reasonable_smoke');
assert(isfile(fullfile(output_root, 'batch_results.csv')), 'Reasonable flow should write batch_results.csv.');
assert(isfile(fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat')), 'Reasonable flow should write PSF_fitted_2D_FOVstack.mat.');
assert(isfile(fullfile(output_root, 'reasonable_config.json')), 'Reasonable flow should write reasonable_config.json.');

config = jsondecode(fileread(fullfile(output_root, 'reasonable_config.json')));
assert(isfield(config, 'prealign_search_step') && abs(config.prealign_search_step - 0.25) < 1e-9, ...
    'Reasonable flow should default to prealign_search_step = 0.25.');
assert(isfield(config, 'lock_tilt') && config.lock_tilt == true, ...
    'Reasonable flow should keep tilt locked by default.');
assert(isfield(config, 'pre_alignment') && config.pre_alignment == true, ...
    'Reasonable flow should enable prealignment by default.');
tbl = readtable(fullfile(output_root, 'batch_results.csv'), TextType = "string");
assert(height(tbl) == 1, 'Reasonable smoke fixture should preserve a one-image batch result.');
end
