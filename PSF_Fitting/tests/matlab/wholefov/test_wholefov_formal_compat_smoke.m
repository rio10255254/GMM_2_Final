function test_wholefov_formal_compat_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
addpath(project_root);

output_root = fullfile(project_root, 'tests', 'artifacts', 'wholefov_formal_smoke');
if ~exist(output_root, 'dir')
    mkdir(output_root);
end

candidate_root = fullfile(project_root, 'PSF_Fitting_ValidationLab', 'outputs', 'reasonable_smoke');
assert(isfile(fullfile(candidate_root, 'batch_results.csv')), 'Tracked reasonable_smoke fixture should exist.');

summary = HDR_fitting_2D_WholeFOV_impl( ...
    'subset_indices', [1], ...
    'grid_rows', 1, ...
    'grid_cols', 1, ...
    'use_gpu', false, ...
    'output_root', output_root, ...
    'reuse_candidate_output_root', candidate_root);

assert(isfile(fullfile(output_root, 'batch_results.csv')), 'Formal flow should write batch_results.csv.');
assert(isfile(fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat')), 'Formal flow should write PSF_fitted_2D_FOVstack.mat.');
assert(isfile(fullfile(output_root, 'formal_config.json')), 'Formal flow should write formal_config.json.');

tbl = readtable(fullfile(output_root, 'batch_results.csv'), TextType = "string");
assert(isequal(string(tbl.Properties.VariableNames), ["filename", "fval", "iterations", "seconds"]), ...
    'Formal batch_results.csv should keep the legacy four-column schema.');
assert(height(tbl) == 1, 'Formal compat smoke should preserve a one-image fixture result.');

stack = load(fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat'));
assert(isequal(size(stack.psf_grid), [101, 101]) || isequal(size(stack.psf_grid), [101, 101, 1, 1]), ...
    'Formal stack should preserve grid-shaped layout.');
assert(isfield(stack, 'coef_grid') && (isequal(size(stack.coef_grid), [15, 1]) || isequal(size(stack.coef_grid), [15, 1, 1])), ...
    'Formal stack should preserve coef_grid layout.');
assert(isfield(stack, 'fval_map') && isequal(size(stack.fval_map), [1, 1]), ...
    'Formal stack should preserve fval_map layout.');
assert(isfield(stack, 'iterations_map') && isequal(size(stack.iterations_map), [1, 1]), ...
    'Formal stack should preserve iterations_map layout.');
assert(isfield(stack, 'filename_map') && isequal(size(stack.filename_map), [1, 1]), ...
    'Formal stack should preserve filename_map layout.');
assert(summary.num_images == 1, 'Formal smoke summary should report one image.');
end
