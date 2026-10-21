function test_manual_psf_fitting_entrypoint_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
addpath(project_root);

manual_entrypoint = fullfile(project_root, 'run_psf_fitting_manual.m');
assert(isfile(manual_entrypoint), 'Manual PSF fitting entrypoint should exist at the project root.');

candidate_root = fullfile(project_root, 'PSF_Fitting_ValidationLab', 'outputs', 'reasonable_smoke');
assert(isfile(fullfile(candidate_root, 'batch_results.csv')), 'Tracked reasonable_smoke fixture should exist.');

output_root = fullfile(project_root, 'tests', 'artifacts', 'manual_psf_fitting_smoke');
if ~exist(output_root, 'dir')
    mkdir(output_root);
end

summary = run_psf_fitting_manual( ...
    'subset_indices', 1, ...
    'grid_rows', 1, ...
    'grid_cols', 1, ...
    'use_gpu', false, ...
    'output_root', output_root, ...
    'reuse_candidate_output_root', candidate_root);

assert(isfile(fullfile(output_root, 'batch_results.csv')), 'Manual entrypoint should write batch_results.csv.');
assert(isfile(fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat')), 'Manual entrypoint should write PSF_fitted_2D_FOVstack.mat.');
assert(isfile(fullfile(output_root, 'formal_config.json')), 'Manual entrypoint should write formal_config.json.');
assert(summary.num_images == 1, 'Manual smoke summary should report one image.');
assert(contains(summary.stack_path, "PSF_fitted_2D_FOVstack.mat"), 'Manual summary should point to the fitted PSF stack.');

relative_output_root = fullfile('tests', 'artifacts', 'manual_psf_fitting_from_elsewhere');
project_relative_output_root = fullfile(project_root, relative_output_root);
if exist(project_relative_output_root, 'dir')
    rmdir(project_relative_output_root, 's');
end

original_pwd = pwd;
cleanup = onCleanup(@() cd(original_pwd)); %#ok<NASGU>
cd(tempdir);

summary_from_elsewhere = run_psf_fitting_manual( ...
    'subset_indices', 1, ...
    'grid_rows', 1, ...
    'grid_cols', 1, ...
    'use_gpu', false, ...
    'output_root', relative_output_root, ...
    'reuse_candidate_output_root', candidate_root);

assert(isfile(fullfile(project_relative_output_root, 'PSF_fitted_2D_FOVstack.mat')), ...
    'Manual entrypoint should resolve relative outputs from the PSF project root.');
assert(startsWith(summary_from_elsewhere.stack_path, string(project_relative_output_root)), ...
    'Manual summary should report the resolved project-root output path.');
end
