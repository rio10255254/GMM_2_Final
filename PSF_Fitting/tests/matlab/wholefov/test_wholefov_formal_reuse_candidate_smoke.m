function test_wholefov_formal_reuse_candidate_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
addpath(project_root);
addpath(fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts'));

candidate_root = fullfile(project_root, 'PSF_Fitting_ValidationLab', 'outputs', 'reasonable_smoke');
assert(isfile(fullfile(candidate_root, 'batch_results.csv')), 'Tracked reasonable_smoke fixture should exist.');

output_root = fullfile(project_root, 'tests', 'artifacts', 'wholefov_formal_reuse_smoke');
if ~exist(output_root, 'dir')
    mkdir(output_root);
end

summary = HDR_fitting_2D_WholeFOV_impl( ...
    'subset_indices', [1], ...
    'grid_rows', 1, ...
    'grid_cols', 1, ...
    'output_root', output_root, ...
    'reuse_candidate_output_root', candidate_root);

assert(isfile(fullfile(output_root, 'batch_results.csv')), 'Formal reuse path should write batch_results.csv.');
assert(isfile(fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat')), 'Formal reuse path should write PSF_fitted_2D_FOVstack.mat.');
assert(summary.num_images == 1, 'Formal reuse smoke summary should report one image.');
end
