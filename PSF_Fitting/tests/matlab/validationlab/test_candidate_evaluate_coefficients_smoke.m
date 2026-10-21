function test_candidate_evaluate_coefficients_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
scripts_dir = fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts');
addpath(scripts_dir);

output_root = fullfile(project_root, 'tests', 'artifacts', 'candidate_eval_coefficients_smoke');
if exist(output_root, 'dir')
    rmdir(output_root, 's');
end
mkdir(output_root);

coef_path = fullfile(output_root, 'coefficient_cases.csv');
coef = zeros(1, 15);
coef(15) = 1.0;
tbl = array2table(coef, 'VariableNames', compose("x%d", 1:15));
tbl = addvars(tbl, string("ideal_fov61"), 61, 'Before', 1, ...
    'NewVariableNames', {'case_id', 'file_index'});
writetable(tbl, coef_path);

input_folder = fullfile(project_root, 'quick_recalibration', 'validation_experiments', ...
    'L0_newdata_round1', 'inputs_primary');
gt_path = fullfile(input_folder, 'GT', 'GT_901_with_Block_proc.bmp');
loss_mask_path = fullfile(input_folder, 'GT', 'circle_edge_mask.bmp');

summary = HDR_fitting_2D_WholeFOV_candidate_prealign( ...
    'mode', 'evaluate_coefficients', ...
    'coefficient_csv_path', coef_path, ...
    'input_folder', input_folder, ...
    'gt_path', gt_path, ...
    'loss_mask_path', loss_mask_path, ...
    'grid_rows', 11, ...
    'grid_cols', 11, ...
    'pre_alignment', false, ...
    'lock_tilt', true, ...
    'use_gpu', false, ...
    'output_root', output_root);

assert(isfield(summary, 'evaluation_results_path'), 'Evaluation summary should expose result CSV path.');
assert(isfile(fullfile(output_root, 'coefficient_evaluation.csv')), 'Coefficient evaluation CSV should be written.');
assert(isfile(fullfile(output_root, 'PSF_evaluated_coefficients.mat')), 'Evaluated PSF stack should be written.');
assert(isfile(fullfile(output_root, 'coefficient_evaluation_config.json')), 'Evaluation config should be written.');

out_tbl = readtable(fullfile(output_root, 'coefficient_evaluation.csv'), TextType = "string");
assert(height(out_tbl) == 1, 'One input coefficient case should produce one output row.');
assert(isfinite(out_tbl.loss(1)), 'Evaluated loss should be finite.');
assert(abs(out_tbl.psf_sum(1) - 1.0) < 1e-9, 'Unit-amplitude PSF should sum to 1.');
assert(ismember("x1", string(out_tbl.Properties.VariableNames)), 'Coefficient columns should be preserved in the output table.');
assert(ismember("x15", string(out_tbl.Properties.VariableNames)), 'Coefficient columns should be preserved in the output table.');
assert(abs(out_tbl.x15(1) - 1.0) < 1e-12, 'Output coefficient columns should match the evaluated coefficient case.');
end
