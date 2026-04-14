function test_validation_lab_aggregate_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(lab_root, 'scripts');

addpath(scripts_dir);

experiment_names = ["baseline_rep16", "alignment_rep16", "alignment_tilt_rep16", "alignment_subpixel_rep16"];
output_root = vlab_test_output_root(lab_root);
summary = vlab_aggregate_existing_results(lab_root, 'experiment_names', experiment_names, 'output_root', output_root);

comparison_path = fullfile(output_root, 'tables', 'experiment_comparison.csv');
assert(isfile(comparison_path), 'comparison csv should be regenerated.');

comparison_tbl = readtable(comparison_path, TextType = "string");
assert(height(comparison_tbl) == 4, 'Expected exactly four rep16 experiments.');
assert(all(ismember(experiment_names, comparison_tbl.experiment_name)), ...
    'Completed experiments missing from comparison table.');

alignment_row = comparison_tbl(comparison_tbl.experiment_name == "alignment_rep16", :);
subpixel_row = comparison_tbl(comparison_tbl.experiment_name == "alignment_subpixel_rep16", :);
assert(~isempty(alignment_row), 'alignment_rep16 should be present.');
assert(~isempty(subpixel_row), 'alignment_subpixel_rep16 should be present.');
assert(subpixel_row.mean_abs_peak_offset < alignment_row.mean_abs_peak_offset, ...
    'Subpixel alignment should improve abs peak offset against integer alignment.');
assert(summary.best_offset_experiment == "alignment_subpixel_rep16", ...
    'Subpixel alignment should win offset comparison.');
end
