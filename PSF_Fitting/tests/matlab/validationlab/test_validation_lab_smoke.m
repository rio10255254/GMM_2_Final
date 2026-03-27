function test_validation_lab_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
root_dir = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(root_dir, 'scripts');

addpath(scripts_dir);

experiment_configs = vlab_get_experiment_configs(root_dir); %#ok<NASGU>

assert(~isempty(experiment_configs), 'Experiment config list should not be empty.');
assert(numel(experiment_configs) >= 3, 'Expected at least three experiment configs.');
end
