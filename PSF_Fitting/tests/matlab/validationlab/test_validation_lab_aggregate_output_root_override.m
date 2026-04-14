function test_validation_lab_aggregate_output_root_override()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(lab_root, 'scripts');

addpath(scripts_dir);

temp_outputs_root = fullfile(tempdir, ['vlab_aggregate_override_' char(java.util.UUID.randomUUID)]);
source_experiment_root = fullfile(lab_root, 'outputs', 'experiments', 'alignment_subpixel_rep16');
target_experiment_root = fullfile(temp_outputs_root, 'experiments', 'alignment_subpixel_rep16');

mkdir(fullfile(temp_outputs_root, 'experiments'));
copyfile(source_experiment_root, target_experiment_root);

summary = vlab_aggregate_existing_results(lab_root, ...
    'experiment_names', "alignment_subpixel_rep16", ...
    'output_root', temp_outputs_root);

assert(isfile(fullfile(temp_outputs_root, 'reports', 'validation_summary_tw.md')), ...
    'Aggregate override should write validation summary into the requested output root.');
assert(isfile(fullfile(temp_outputs_root, 'tables', 'experiment_comparison.csv')), ...
    'Aggregate override should write comparison table into the requested output root.');
assert(contains(summary.validation_summary_path, temp_outputs_root), ...
    'Summary payload should point to the override output root.');
end
